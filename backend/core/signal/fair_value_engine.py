"""
Fair value computation with oracle risk discount.

Oracle risk buffer per audit:
- Category-A markets (sports scores, official govt data): 0.5%
- Other markets: 2.0%
"""
from decimal import Decimal
from config.settings import settings


class FairValueEngine:
    def __init__(
        self,
        oracle_risk_buffer_a: float = None,
        oracle_risk_buffer_default: float = None,
    ):
        self.risk_buffer_a = Decimal(str(oracle_risk_buffer_a or settings.oracle_risk_buffer_a))
        self.risk_buffer_default = Decimal(str(oracle_risk_buffer_default or settings.oracle_risk_buffer_default))

    def compute_fair_value(self, confirmed_outcome_price: Decimal, category: str) -> Decimal:
        """
        Fair value = confirmed_outcome_price * (1 - oracle_risk_buffer)

        For YES share resolving at $1.00:
          Category-A: fair_value = 1.00 * (1 - 0.005) = $0.995
          Default:     fair_value = 1.00 * (1 - 0.020) = $0.980
        """
        buffer = self.risk_buffer_a if category == "A" else self.risk_buffer_default
        return confirmed_outcome_price * (Decimal("1.0") - buffer)

    def net_edge_cents(self, entry_price: Decimal, fair_value: Decimal) -> float:
        """Net edge after oracle risk discount, in cents."""
        return float((fair_value - entry_price) * 100)
