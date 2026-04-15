"""
Slippage and fill probability model calibrated to Polymarket CLOB microstructure.

Audit fix: original used a binary filled/not-filled model.
Real fill rate decays with queue position and resolution proximity.
"""
from decimal import Decimal


class SlippageFillModel:
    """
    Fill probability based on queue position, market activity, and resolution proximity.
    Calibrated to binary prediction market microstructure, not equity models.
    """

    def fill_probability(
        self,
        queue_pos: int,
        book_depth_at_price: Decimal,
        daily_volume_usd: float,
        time_to_resolution_hrs: float,
    ) -> float:
        """
        Returns probability (0.0–0.95) that a resting order at queue_pos fills.

        Factors:
        - Queue depth: deeper queue = lower fill rate
        - Volume: more activity = more queue churn = higher fill rate
        - Resolution proximity: everyone pulls quotes near resolution → lower fill rate
        """
        # Base fill rate decays with queue position
        base = 1.0 / (1.0 + 0.4 * queue_pos)

        # Volume adjustment: more activity = more queue churn
        vol_adj = min(1.5, daily_volume_usd / 50_000)

        # Resolution proximity: books thin out near resolution
        if time_to_resolution_hrs < 4:
            resolution_adj = 0.5  # everyone pulling quotes
        elif time_to_resolution_hrs < 24:
            resolution_adj = 0.8
        else:
            resolution_adj = 1.0

        return min(0.95, base * vol_adj * resolution_adj)

    def expected_slippage(self, order_size_usd: float, book_depth_usd: float) -> Decimal:
        """
        Expected slippage for a market order of given size.
        Empirically calibrated for Polymarket thin books:
          slippage ≈ 0.08 * (order_size / book_depth)^0.6
        """
        if book_depth_usd <= 0:
            return Decimal("0.10")  # assume 10% slippage on empty book

        consumption_ratio = order_size_usd / max(book_depth_usd, 1)
        slippage = 0.08 * (consumption_ratio ** 0.6)
        return Decimal(str(round(slippage, 4)))
