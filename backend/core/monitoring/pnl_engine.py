"""P&L engine: rolling Sharpe ratio, strategy attribution."""
from collections import defaultdict, deque
from datetime import datetime
import math
from typing import Optional


class PnLEngine:
    def __init__(self, window_days: int = 7):
        self._daily_returns: deque[float] = deque(maxlen=window_days * 24)
        self._strategy_pnl: dict[str, float] = defaultdict(float)
        self._total_realized: float = 0.0

    def record_trade(self, strategy: str, pnl: float):
        self._total_realized += pnl
        self._strategy_pnl[strategy] += pnl
        self._daily_returns.append(pnl)

    @property
    def sharpe_ratio(self) -> Optional[float]:
        if len(self._daily_returns) < 10:
            return None
        returns = list(self._daily_returns)
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance)
        if std == 0:
            return None
        return (mean / std) * math.sqrt(252)  # annualized

    def summary(self) -> dict:
        return {
            "total_realized": self._total_realized,
            "sharpe_ratio": self.sharpe_ratio,
            "strategy_attribution": dict(self._strategy_pnl),
        }
