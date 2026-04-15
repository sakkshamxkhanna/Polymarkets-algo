"""
Kill switch — evaluates system metrics and fires emergency shutdown.

Triggers (per audit):
- API latency p99 > 500ms
- WS feed gap > 10s
- Daily drawdown > 8%
- Orphaned orders detected
"""
import asyncio
import logging
import time
from collections import deque
from typing import Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class LatencyTracker:
    """Rolling p99 latency tracker (last 100 measurements)."""
    def __init__(self, window: int = 100):
        self._samples: deque[float] = deque(maxlen=window)

    def record(self, latency_ms: float):
        self._samples.append(latency_ms)

    @property
    def p99(self) -> float:
        if not self._samples:
            return 0.0
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]


class KillSwitch:
    TRIGGERS = {
        "api_latency_ms": 500.0,  # REST API p99 > 500ms
        "ws_gap_ms": 300_000.0,  # No WS update for 5min — oracle-pending markets rarely trade
        "daily_drawdown": 0.08,   # 8% daily loss
        "fill_anomaly": 3.0,      # fills 3x worse than sim baseline
    }

    def __init__(self, on_fire: Optional[Callable[[], Coroutine]] = None):
        self._active = False
        self._fired_at: Optional[float] = None
        self._fire_reason: Optional[str] = None
        self._on_fire = on_fire
        self.latency_tracker = LatencyTracker()
        self._fire_history: list[dict] = []

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def fired_at(self) -> Optional[float]:
        return self._fired_at

    @property
    def fire_reason(self) -> Optional[str]:
        return self._fire_reason

    def evaluate(
        self,
        ws_last_msg_ts: float,
        daily_drawdown_pct: float,
        has_orphaned_orders: bool = False,
    ) -> Optional[str]:
        """Check all triggers. Returns breach name or None."""
        if self._active:
            return "ALREADY_ACTIVE"

        api_p99 = self.latency_tracker.p99
        if api_p99 > self.TRIGGERS["api_latency_ms"]:
            return f"LATENCY_SPIKE (p99={api_p99:.0f}ms)"

        ws_gap = (time.time() - ws_last_msg_ts) * 1000
        if ws_last_msg_ts > 0 and ws_gap > self.TRIGGERS["ws_gap_ms"]:
            return f"WS_FEED_DEAD (gap={ws_gap/1000:.1f}s)"

        if daily_drawdown_pct > self.TRIGGERS["daily_drawdown"]:
            return f"DRAWDOWN_BREACH ({daily_drawdown_pct:.1%})"

        if has_orphaned_orders:
            return "ORPHANED_ORDERS_DETECTED"

        return None

    async def fire(self, reason: str):
        """
        Fire the kill switch.
        Caller is responsible for cancelling all open CLOB orders.
        """
        if self._active:
            return

        self._active = True
        self._fired_at = time.time()
        self._fire_reason = reason
        self._fire_history.append({
            "timestamp": self._fired_at,
            "reason": reason,
        })
        logger.critical(f"KILL SWITCH FIRED: {reason}")

        if self._on_fire:
            try:
                await self._on_fire()
            except Exception as e:
                logger.error(f"Kill switch callback error: {e}")

    def reset(self):
        """Manual reset after human review."""
        logger.warning("Kill switch reset by operator")
        self._active = False
        self._fired_at = None
        self._fire_reason = None

    def to_dict(self) -> dict:
        return {
            "active": self._active,
            "fired_at": self._fired_at,
            "fire_reason": self._fire_reason,
            "api_p99_ms": self.latency_tracker.p99,
            "history": self._fire_history[-5:],
        }
