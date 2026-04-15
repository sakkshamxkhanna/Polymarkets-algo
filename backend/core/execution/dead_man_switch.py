"""
Dead-man switch: if heartbeat is missed for >60s, cancels all registered GTC orders.
Prevents orphaned orders accumulating inventory when process crashes or network drops.
"""
import asyncio
import logging
import time
from typing import Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 30.0
MAX_HEARTBEAT_GAP_S = 60.0


class DeadManSwitch:
    def __init__(self, cancel_all_fn: Callable[[], Coroutine]):
        self._cancel_all = cancel_all_fn
        self._last_heartbeat: float = time.time()
        self._running = False
        self._fired = False

    def heartbeat(self):
        """Call this every 30s from the main trading loop."""
        self._last_heartbeat = time.time()

    @property
    def gap_seconds(self) -> float:
        return time.time() - self._last_heartbeat

    async def run(self):
        """Monitor heartbeat in background. Fire if gap exceeds threshold."""
        self._running = True
        while self._running:
            await asyncio.sleep(5.0)  # check every 5s
            gap = self.gap_seconds
            if gap > MAX_HEARTBEAT_GAP_S and not self._fired:
                self._fired = True
                logger.critical(
                    f"Dead-man switch firing! Heartbeat gap = {gap:.1f}s > {MAX_HEARTBEAT_GAP_S}s"
                )
                try:
                    await self._cancel_all()
                except Exception as e:
                    logger.error(f"Dead-man cancel-all error: {e}")

    async def stop(self):
        self._running = False

    def reset(self):
        self._fired = False
        self._last_heartbeat = time.time()
