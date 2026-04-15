"""
Real-time position and P&L tracking.
Tracks unrealized + realized P&L across all open positions.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OpenPosition:
    token_id: str
    market_id: str
    question: str
    side: str  # YES / NO
    entry_price: Decimal
    current_price: Decimal
    size_usdc: Decimal
    strategy: str = "resolution_timing"
    opened_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_long(self) -> bool:
        return True  # Resolution timing always buys

    @property
    def unrealized_pnl(self) -> Decimal:
        # Shares held = size_usdc / entry_price
        shares = self.size_usdc / self.entry_price
        return (self.current_price - self.entry_price) * shares

    @property
    def notional(self) -> Decimal:
        return self.size_usdc


class PositionLedger:
    def __init__(self, total_capital: float):
        self.total_capital = Decimal(str(total_capital))
        self.positions: dict[str, OpenPosition] = {}  # token_id -> Position
        self._realized_pnl: Decimal = Decimal("0")
        self._daily_realized_pnl: Decimal = Decimal("0")
        self._day_start: datetime = datetime.utcnow().replace(hour=0, minute=0, second=0)

    def _check_day_reset(self):
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if today_start > self._day_start:
            self._daily_realized_pnl = Decimal("0")
            self._day_start = today_start

    @property
    def total_notional(self) -> Decimal:
        return sum(p.notional for p in self.positions.values())

    @property
    def unrealized_pnl(self) -> Decimal:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    @property
    def daily_pnl(self) -> Decimal:
        self._check_day_reset()
        return self._daily_realized_pnl + self.unrealized_pnl

    @property
    def worst_case_loss(self) -> Decimal:
        """All positions resolve against us simultaneously."""
        return -sum(p.size_usdc for p in self.positions.values())

    def open_position(self, position: OpenPosition):
        self.positions[position.token_id] = position
        logger.info(
            f"Position opened: {position.side} {position.market_id} "
            f"@ {position.entry_price} size={position.size_usdc} USDC"
        )

    def update_price(self, token_id: str, current_price: Decimal):
        if token_id in self.positions:
            self.positions[token_id].current_price = current_price

    def close_position(self, token_id: str, fill_price: Decimal) -> Optional[Decimal]:
        if token_id not in self.positions:
            return None
        pos = self.positions.pop(token_id)
        shares = pos.size_usdc / pos.entry_price
        pnl = (fill_price - pos.entry_price) * shares
        self._realized_pnl += pnl
        self._daily_realized_pnl += pnl
        # Compound: re-invest gains (or absorb losses) into total capital so
        # future Kelly-sized positions grow with the bankroll.
        self.total_capital += pnl
        logger.info(
            f"Position closed: {token_id} pnl={pnl:+.4f} USDC "
            f"→ new bankroll ${float(self.total_capital):.2f}"
        )
        return pnl

    def check_kill_conditions(self) -> Optional[str]:
        """Returns breach type string or None if all clear."""
        self._check_day_reset()
        daily = self.daily_pnl
        if daily < -(self.total_capital * Decimal("0.08")):
            return "DAILY_DRAWDOWN_BREACH"
        if self.total_notional > self.total_capital * Decimal("1.20"):
            return "NOTIONAL_OVEREXTENSION"
        return None

    def can_open_position(
        self,
        size_usdc: float,
        max_positions: int = 20,
        max_pct: float = 0.03,
    ) -> tuple[bool, str]:
        """
        Check if a new position can be opened given risk limits.

        max_pct controls the per-position capital cap:
          0.03  → oracle-lag / resolution-timing (default, conservative)
          0.40  → velocity-momentum (aggressive Kelly compounding path)
        """
        size = Decimal(str(size_usdc))
        pct = size / max(self.total_capital, Decimal("1"))
        cap = Decimal(str(max_pct))
        if pct > cap:
            return False, f"Position size {float(pct):.1%} exceeds {max_pct:.0%} capital cap"
        if len(self.positions) >= max_positions:
            return False, f"Max concurrent positions ({max_positions}) reached"
        new_notional = self.total_notional + size
        if new_notional > self.total_capital * Decimal("0.90"):
            return False, f"Adding ${float(size):.2f} would deploy {float(new_notional/self.total_capital):.0%} of capital (>90% limit)"
        if self.check_kill_conditions() is not None:
            return False, "Kill switch conditions active"
        return True, "OK"

    def to_dict(self) -> dict:
        return {
            "total_capital": float(self.total_capital),
            "total_notional": float(self.total_notional),
            "unrealized_pnl": float(self.unrealized_pnl),
            "realized_pnl": float(self.realized_pnl),
            "daily_pnl": float(self.daily_pnl),
            "position_count": len(self.positions),
            "positions": [
                {
                    "token_id": p.token_id,
                    "market_id": p.market_id,
                    "question": p.question,
                    "side": p.side,
                    "entry_price": float(p.entry_price),
                    "current_price": float(p.current_price),
                    "size_usdc": float(p.size_usdc),
                    "unrealized_pnl": float(p.unrealized_pnl),
                    "strategy": p.strategy,
                    "opened_at": p.opened_at.isoformat(),
                }
                for p in self.positions.values()
            ],
        }
