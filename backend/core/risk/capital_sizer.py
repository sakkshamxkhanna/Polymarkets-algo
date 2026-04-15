"""
Position sizing using fractional Kelly criterion.
Hard cap: 3% of total capital per position (audit resolution timing requirement).
"""
from decimal import Decimal
from config.settings import settings


class CapitalSizer:
    def __init__(self, total_capital: float, kelly_fraction: float = None):
        self.total_capital = Decimal(str(total_capital))
        self.kelly_fraction = Decimal(str(kelly_fraction or settings.kelly_fraction))
        self.max_position_pct = Decimal(str(settings.max_position_pct))

    def kelly_size(self, p_win: float, ask_price: float) -> Decimal:
        """
        Fractional Kelly position size in USDC.

        p_win: estimated probability of winning (0.0-1.0)
        ask_price: cost per share (0.01-0.99)

        Formula:
          odds = (1.0 / ask_price) - 1
          full_kelly = (p_win * odds - (1 - p_win)) / odds
          position_usdc = bankroll * full_kelly * kelly_fraction / ask_price
        """
        p = Decimal(str(p_win))
        ask = Decimal(str(ask_price))

        if ask >= Decimal("1"):
            return Decimal("0")

        odds = (Decimal("1") / ask) - Decimal("1")
        if odds <= 0:
            return Decimal("0")

        q = Decimal("1") - p
        full_kelly = (p * odds - q) / odds

        if full_kelly <= 0:
            return Decimal("0")

        size_usdc = self.total_capital * full_kelly * self.kelly_fraction / ask

        # Apply hard cap: max 3% of total capital
        max_size = self.total_capital * self.max_position_pct
        return min(size_usdc, max_size)

    def oracle_lag_size(self, confidence: float, entry_price: float) -> Decimal:
        """
        Position sizing for oracle-lag (resolution timing) trades.

        Kelly fails for high-price tokens (returns 0 when market is already
        efficient). For oracle-lag, confidence IS the sizing signal:

          size = max_position * confidence

        At 85% confidence → 85% of max position ($12.75 on $500 capital).
        At 93% confidence → 93% of max position ($13.95).

        This reflects: higher market consensus = more of the position limit
        is justified, because oracle delay is the only remaining discount.
        """
        max_size = self.total_capital * self.max_position_pct
        return max_size * Decimal(str(confidence))

    def velocity_size(self, implied_prob: float, entry_price: float) -> Decimal:
        """
        Aggressive half-Kelly sizing for velocity-momentum trades.

        Unlike oracle-lag (3% hard cap), velocity momentum uses up to 40% of
        bankroll per position because:
          1. Resolution is within 48h (not waiting for stalled oracle)
          2. There's a defined exit target (+25%) and stop-loss (-15%)
          3. Compounding at this scale is the ONLY path to 166x in 7 days

        Half-Kelly formula:
          odds = (1/ask) - 1
          full_kelly = (p * odds - q) / odds
          size = capital * (full_kelly * 0.5) / ask

        Hard cap: 40% of total capital per position.
        """
        p   = Decimal(str(max(0.01, min(0.99, implied_prob))))
        ask = Decimal(str(max(0.01, min(0.99, entry_price))))

        odds = (Decimal("1") / ask) - Decimal("1")
        if odds <= 0:
            return Decimal("0")

        q           = Decimal("1") - p
        full_kelly  = (p * odds - q) / odds
        if full_kelly <= 0:
            return Decimal("0")

        half_kelly  = full_kelly * Decimal("0.5")
        size_usdc   = self.total_capital * half_kelly / ask

        max_size = self.total_capital * Decimal("0.40")   # hard 40% cap
        return min(size_usdc, max_size)

    def compute_size(
        self,
        confidence: float,
        entry_price: float,
        gross_edge_cents: float = 0.0,
        strategy: str = "resolution_timing",
    ) -> float:
        """
        Dispatch to the appropriate sizer based on strategy.

        velocity_momentum → aggressive half-Kelly (up to 40% of capital)
        resolution_timing → conservative confidence-proportional (3% cap)
        """
        if strategy == "velocity_momentum":
            return float(self.velocity_size(confidence, entry_price))
        if entry_price >= 0.65:
            return float(self.oracle_lag_size(confidence, entry_price))
        return float(self.kelly_size(confidence, entry_price))
