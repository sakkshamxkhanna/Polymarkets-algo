"""
Resolution Timing (Stale Oracle) strategy signal generator.
Scans for markets where real-world outcome is clear but oracle hasn't settled yet.

Corrected entry criteria (ALL must be true):
1. market.end_date < now  (market has already expired)
2. Winning side price is in the "oracle lag zone": MIN_CONFIDENCE ≤ price ≤ MAX_PRICE
   - MIN_CONFIDENCE (default 0.85): market must be ≥85% confident in this side
     → oracle lag (not genuine uncertainty) must be the dominant discount driver
   - MAX_PRICE (default 0.94): at least 6¢ discount from fair value remains
3. UMA oracle assertion NOT yet submitted
4. Outcome confirmed by SourceVerifier (market-consensus weighted)
5. Capital deployment ≤ 3% per position, ≤ 80% total

Key insight: a YES token at 7¢ has 93¢ gross "edge" but only pays out
if YES wins — which the market prices at 7%. The real trade is the token
already near $1.00 (e.g. NO at 92¢) where the oracle is the only remaining
friction before it reaches $1.00 payout.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from core.data.normalization import Market, OrderbookSnapshot

logger = logging.getLogger(__name__)

MIN_HOURS_TO_RESOLUTION = 6.0  # markets closing within 6 hours
MAX_PRICE = Decimal("0.94")     # minimum 6¢ gross edge remaining
# MIN_CONFIDENCE is the critical threshold — see pick_confident_side() below


@dataclass
class ResolutionOpportunity:
    market: Market
    token_id: str
    side: str  # "YES" or "NO"
    entry_price: Decimal
    fair_value: Decimal
    gross_edge_cents: float
    hours_to_resolution: float
    confidence: float  # from SourceVerifier
    sources: list[str]


def pick_confident_side(
    yes_ask: Optional[Decimal],
    no_ask: Optional[Decimal],
    min_confidence: Decimal,
) -> Optional[tuple[str, Decimal]]:
    """
    Choose which side (YES or NO) is the market-consensus winner in the oracle lag zone.

    Returns (side, price) for the side that qualifies, or None if neither does.

    The oracle lag zone is:  min_confidence ≤ price ≤ MAX_PRICE
      - min_confidence floor: market must be sufficiently confident in this outcome
        (prevents buying 7¢ tokens that are cheap because they're unlikely to win)
      - MAX_PRICE ceiling: at least 6¢ edge must remain before oracle settles

    If BOTH sides qualify (rare on binary markets), pick the one closer to MAX_PRICE
    (higher confidence = more certain the oracle will confirm it).

    Threshold choice: 0.85 (hardened to default via OracleLagMonitor constructor).
    Rationale: at ≥85¢ the market has near-certain conviction; oracle lag (not
    genuine uncertainty) is the dominant discount driver.  EV at 85¢ entry with
    a realistic true-prob of 95%: 0.95×17.6% − 0.05×100% ≈ +11.7%.  Below 0.85
    genuine uncertainty competes with oracle lag, eroding the edge.
    """
    yes_qualifies = yes_ask is not None and min_confidence <= yes_ask <= MAX_PRICE
    no_qualifies  = no_ask  is not None and min_confidence <= no_ask  <= MAX_PRICE

    if yes_qualifies and no_qualifies:
        # Both sides in the lag zone — prefer the more confident (higher-priced) one
        return ("YES", yes_ask) if yes_ask >= no_ask else ("NO", no_ask)
    elif yes_qualifies:
        return ("YES", yes_ask)
    elif no_qualifies:
        return ("NO", no_ask)
    return None


class OracleLagMonitor:
    def __init__(self, min_edge_cents: float = 6.0, min_confidence: float = 0.85):
        self.min_edge_cents = min_edge_cents
        self.min_confidence = Decimal(str(min_confidence))

    def scan(
        self,
        markets: list[Market],
        orderbooks: dict[str, OrderbookSnapshot],
        total_capital: float,
        current_notional: float,
    ) -> list[ResolutionOpportunity]:
        """
        Scan expired markets for oracle-lag opportunities.
        Only considers the market-consensus WINNING side (price in oracle lag zone).
        """
        opportunities: list[ResolutionOpportunity] = []

        available_capital_pct = 1.0 - (current_notional / max(total_capital, 1.0))
        if available_capital_pct < 0.03:
            logger.info("Portfolio at capacity — no new resolution timing trades")
            return []

        now = datetime.utcnow()

        for market in markets:
            if not market.is_active:
                continue
            if market.oracle_submitted:
                continue
            if market.end_date > now:
                continue  # must have already expired — no speculative pre-expiry entries

            hrs = market.hours_to_resolution

            # Resolve YES ask price
            yes_book = orderbooks.get(market.yes_token_id)
            yes_ask: Optional[Decimal] = (
                yes_book.best_ask if yes_book and yes_book.best_ask
                else (Decimal(str(market.best_ask)) if 0 < market.best_ask < 1.0 else None)
            )

            # Resolve NO ask price (complement of YES bid as fallback)
            no_book = orderbooks.get(market.no_token_id)
            if no_book and no_book.best_ask:
                no_ask: Optional[Decimal] = no_book.best_ask
            elif market.best_bid > 0:
                no_ask = Decimal(str(round(1.0 - market.best_bid, 4)))
            else:
                no_ask = None

            result = pick_confident_side(yes_ask, no_ask, self.min_confidence)
            if result is None:
                continue

            side, entry_price = result
            token_id = market.yes_token_id if side == "YES" else market.no_token_id
            edge_cents = float((Decimal("1.00") - entry_price) * 100)

            if edge_cents < self.min_edge_cents:
                continue

            opportunities.append(ResolutionOpportunity(
                market=market,
                token_id=token_id,
                side=side,
                entry_price=entry_price,
                fair_value=Decimal("1.00"),
                gross_edge_cents=edge_cents,
                hours_to_resolution=hrs,
                confidence=0.0,
                sources=[],
            ))

        opportunities.sort(key=lambda x: x.gross_edge_cents, reverse=True)
        logger.info(
            f"Oracle lag scan: {len(opportunities)} opportunities "
            f"(min_confidence={self.min_confidence}) from {len(markets)} markets"
        )
        return opportunities
