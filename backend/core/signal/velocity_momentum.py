"""
Velocity Momentum Strategy — real-time mispricing detector for active markets.

UNLIKE the oracle-lag strategy (which trades expired markets waiting for UMA
oracle assertions that take weeks/months), Velocity Momentum:

1. Targets ACTIVE markets closing within 48 hours
2. Uses real-time CoinGecko prices to compute a log-normal implied probability
3. Enters when implied_prob - market_price >= MIN_EDGE (18%)
4. Exits at +25% gain target or -15% stop-loss (NOT at oracle resolution)
5. Uses half-Kelly sizing capped at 40% of capital per trade — the ONLY path
   to compounding $300 → $50,000 in a week

Why 18% minimum edge:
  - Transaction costs on Polymarket: ~1-2%
  - Slippage: ~1%
  - Net edge after friction: 15%+ — strongly positive EV
  - Below 18% gross, friction erodes too much of the edge

Market question parsing examples (auto-detected):
  "Will Bitcoin be above $100,000 at the end of April?"  → BTC above $100k
  "Will ETH exceed $3,500 by May 31?"                   → ETH above $3500
  "Will BTC close below $80k this week?"                → BTC below $80k
  "Bitcoin price above $110,000 on 4/20/25?"            → BTC above $110k
"""
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from core.data.normalization import Market
from core.data.crypto_price_feed import CryptoPriceFeed

logger = logging.getLogger(__name__)

# ── Strategy parameters ────────────────────────────────────────────────────────
MIN_EDGE        = 0.15    # minimum (implied_prob - market_price) to generate signal
MIN_VOLUME_USD  = 1_000   # skip illiquid markets (lowered — early markets start thin)
MAX_HOURS       = 72.0    # trade markets with ≤72h to close (3 days)
MIN_HOURS       = 0.5     # need at least 30 min for order to fill
TAKE_PROFIT_PCT = 0.25    # exit when price gains 25% from entry
STOP_LOSS_PCT   = 0.15    # exit when price drops 15% from entry
MAX_HOLD_HOURS  = 24.0    # time-based exit regardless of price

# Historical annualized-vol / sqrt(365) → daily vol per asset
# Source: 90-day realised vol averages (conservative, use upper quartile)
DAILY_VOLS: dict[str, float] = {
    "BTC":   0.035,
    "ETH":   0.045,
    "SOL":   0.060,
    "BNB":   0.042,
    "XRP":   0.065,
    "DOGE":  0.075,
    "MATIC": 0.070,
    "AVAX":  0.065,
    "LINK":  0.060,
    "UNI":   0.065,
    "ADA":   0.055,
    "DOT":   0.060,
    "LTC":   0.050,
    "BCH":   0.055,
    "ATOM":  0.060,
    "NEAR":  0.070,
    "APT":   0.080,
    "SUI":   0.085,
    "ARB":   0.075,
    "OP":    0.075,
}

# Keyword → symbol mappings (order matters — more specific first)
ASSET_KEYWORDS: list[tuple[str, list[str]]] = [
    ("BTC",   ["bitcoin", " btc "]),
    ("ETH",   ["ethereum", " eth "]),
    ("SOL",   ["solana", " sol "]),
    ("BNB",   [" bnb ", "binance coin"]),
    ("XRP",   [" xrp ", "ripple"]),
    ("DOGE",  ["dogecoin", "doge"]),
    ("MATIC", ["polygon", "matic"]),
    ("AVAX",  ["avalanche", " avax"]),
    ("LINK",  ["chainlink", " link "]),
    ("UNI",   [" uni ", "uniswap"]),
    ("ADA",   ["cardano", " ada "]),
    ("DOT",   ["polkadot", " dot "]),
    ("LTC",   ["litecoin", " ltc "]),
    ("BCH",   ["bitcoin cash", " bch "]),
    ("ATOM",  [" cosmos", " atom "]),
    ("NEAR",  [" near "]),
    ("APT",   ["aptos", " apt "]),
    ("SUI",   [" sui "]),
    ("ARB",   ["arbitrum", " arb "]),
    ("OP",    ["optimism", " op "]),
]

# Plausible price range per asset (rough sanity filter)
PRICE_SANITY: dict[str, tuple[float, float]] = {
    "BTC":   (1_000,    10_000_000),
    "ETH":   (10,       100_000),
    "SOL":   (0.5,      10_000),
    "BNB":   (1,        50_000),
    "XRP":   (0.001,    10_000),
    "DOGE":  (0.0001,   1_000),
    "MATIC": (0.001,    1_000),
    "AVAX":  (0.1,      10_000),
    "LINK":  (0.1,      5_000),
    "UNI":   (0.01,     1_000),
    "ADA":   (0.001,    100),
    "DOT":   (0.01,     10_000),
    "LTC":   (0.1,      100_000),
    "BCH":   (1,        100_000),
    "ATOM":  (0.01,     10_000),
    "NEAR":  (0.01,     1_000),
    "APT":   (0.01,     1_000),
    "SUI":   (0.001,    1_000),
    "ARB":   (0.001,    1_000),
    "OP":    (0.001,    1_000),
}

# Compiled price-extraction regex
_PRICE_RE = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*([kKmM])?')


@dataclass
class VelocityOpportunity:
    market_id: str
    question: str
    token_id: str
    side: str             # "YES" or "NO"
    entry_price: Decimal
    implied_prob: float   # log-normal model output
    edge: float           # implied_prob − market_price
    asset: str
    current_price: float
    threshold_price: float
    direction: str        # "above" | "below"
    hours_to_close: float
    volume_usd: float
    strategy: str = "velocity_momentum"
    exit_target: float = field(init=False)
    stop_price: float = field(init=False)

    def __post_init__(self):
        ep = float(self.entry_price)
        self.exit_target = round(ep * (1 + TAKE_PROFIT_PCT), 4)
        self.stop_price  = round(ep * (1 - STOP_LOSS_PCT), 4)


# ── Math helpers ───────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Standard normal CDF — no scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def compute_lognormal_prob(
    current_price: float,
    threshold_price: float,
    hours_remaining: float,
    daily_vol: float,
    direction: str,
) -> float:
    """
    P(spot crosses threshold by market close) under the log-normal model.

    Uses zero-drift assumption (conservative — no directional bias claimed).
    Formula: P(S_T > K) = N( ln(S/K) / (σ√T) )   where T is in days.

    Returns probability in [0, 1].
    """
    T = max(hours_remaining / 24.0, 1e-9)
    sigma_T = daily_vol * math.sqrt(T)

    if sigma_T < 1e-9:
        if direction == "above":
            return 1.0 if current_price >= threshold_price else 0.0
        return 1.0 if current_price <= threshold_price else 0.0

    log_return = math.log(current_price / threshold_price)
    d = log_return / sigma_T   # d₂ in BS notation

    return _norm_cdf(d) if direction == "above" else _norm_cdf(-d)


# ── Market question parser ─────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[float]:
    """
    Extract a USD price from text.
    Handles: $100k, $100,000, $3.5k, $110K, $2m
    Returns None if no recognisable price found.
    """
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None

    values: list[float] = []
    for num_str, suffix in matches:
        val = float(num_str.replace(",", ""))
        s = suffix.lower()
        if s == "k":
            val *= 1_000
        elif s == "m":
            val *= 1_000_000
        values.append(val)

    return values[0] if values else None


def parse_crypto_market(question: str) -> Optional[tuple[str, str, float]]:
    """
    Parse a Polymarket question into (asset_symbol, direction, threshold_usd).

    Returns None if the question is not a crypto-price-threshold market.

    Examples:
      "Will Bitcoin be above $100k at end of April?" → ("BTC", "above", 100000)
      "Will ETH drop below $2,500 this week?"        → ("ETH", "below", 2500)
    """
    padded = f" {question.lower()} "   # pad so word boundaries work at start/end

    # ── Detect asset ──────────────────────────────────────────────────────────
    asset: Optional[str] = None
    for sym, keywords in ASSET_KEYWORDS:
        if any(kw in padded for kw in keywords):
            asset = sym
            break
    if asset is None:
        return None

    # ── Detect direction ──────────────────────────────────────────────────────
    above_words = ["above", "exceed", "over $", "surpass", "higher than",
                   "reach $", "hit $", "at or above", "≥"]
    below_words = ["below", "under $", "fall below", "drop below",
                   "lower than", "less than", "at or below", "≤"]

    if any(w in padded for w in above_words):
        direction = "above"
    elif any(w in padded for w in below_words):
        direction = "below"
    else:
        return None

    # ── Extract price threshold ───────────────────────────────────────────────
    threshold = _parse_price(question)
    if threshold is None:
        return None

    # Sanity-check against known asset price ranges
    lo, hi = PRICE_SANITY.get(asset, (0.0, 1e12))
    if not (lo <= threshold <= hi):
        logger.debug(f"Price {threshold} out of range [{lo}, {hi}] for {asset} — skip")
        return None

    return (asset, direction, threshold)


# ── Scanner ────────────────────────────────────────────────────────────────────

class VelocityMomentumScanner:
    """
    Scans active Polymarket markets and generates buy signals when the
    log-normal implied probability diverges from the Polymarket price by
    at least MIN_EDGE.

    Key differences vs OracleLagMonitor:
      - OracleLagMonitor: expired markets, waits for UMA oracle (weeks/months)
      - VelocityMomentumScanner: active markets, exits in <24h at price target
    """

    def __init__(
        self,
        min_edge: float = MIN_EDGE,
        max_hours: float = MAX_HOURS,   # default 72h
        price_feed: Optional[CryptoPriceFeed] = None,
    ):
        self.min_edge  = min_edge
        self.max_hours = max_hours
        self.price_feed = price_feed or CryptoPriceFeed()

    async def scan(
        self,
        markets: list[Market],
        total_capital: float,
        current_notional: float,
    ) -> list[VelocityOpportunity]:
        """
        Returns opportunities sorted by edge descending.
        Only markets in the [MIN_HOURS, max_hours] window are considered.
        """
        available_pct = 1.0 - (current_notional / max(total_capital, 1.0))
        if available_pct < 0.05:
            logger.info("Velocity: portfolio at capacity — skipping scan")
            return []

        now = datetime.utcnow()

        # ── Pass 1: identify parseable markets and needed symbols ─────────────
        candidates: list[tuple[Market, str, str, float]] = []
        needed: set[str] = set()

        for market in markets:
            if not market.is_active:
                continue
            if market.end_date <= now:
                continue          # expired → leave for oracle-lag strategy
            if market.volume_usd < MIN_VOLUME_USD:
                continue

            hrs = market.hours_to_resolution
            if hrs < MIN_HOURS or hrs > self.max_hours:
                continue

            parsed = parse_crypto_market(market.question)
            if parsed is None:
                continue

            asset, direction, threshold = parsed
            candidates.append((market, asset, direction, threshold))
            needed.add(asset)

        if not candidates:
            logger.debug("Velocity: no parseable crypto markets in 48h window")
            return []

        # ── Pass 2: fetch real-time prices ───────────────────────────────────
        prices = await self.price_feed.get_prices(list(needed))
        if not prices:
            logger.warning("Velocity: no crypto prices available — skipping cycle")
            return []

        # ── Pass 3: compute edge and build opportunity list ──────────────────
        opportunities: list[VelocityOpportunity] = []

        for market, asset, direction, threshold in candidates:
            spot = prices.get(asset)
            if spot is None:
                continue

            daily_vol   = DAILY_VOLS.get(asset, 0.060)
            implied_yes = compute_lognormal_prob(
                spot, threshold, market.hours_to_resolution, daily_vol, direction
            )

            # Market YES ask price (what you pay to own YES)
            market_yes = float(market.best_ask) if 0 < market.best_ask < 1 else 0.5
            market_no  = round(1.0 - market_yes, 4)

            yes_edge = implied_yes - market_yes
            no_edge  = (1.0 - implied_yes) - market_no

            best_edge = max(yes_edge, no_edge)
            if best_edge < self.min_edge:
                continue

            if yes_edge >= no_edge:
                side       = "YES"
                entry_p    = Decimal(str(round(market_yes, 4)))
                token_id   = market.yes_token_id
                edge       = yes_edge
            else:
                side       = "NO"
                entry_p    = Decimal(str(round(market_no, 4)))
                token_id   = market.no_token_id
                edge       = no_edge

            # Require at least 6¢ upside to $1.00 (covers transaction costs)
            upside_cents = float((Decimal("1.00") - entry_p) * 100)
            if upside_cents < 6.0:
                continue

            opportunities.append(VelocityOpportunity(
                market_id      = market.condition_id,
                question       = market.question,
                token_id       = token_id,
                side           = side,
                entry_price    = entry_p,
                implied_prob   = round(implied_yes if side == "YES" else (1 - implied_yes), 4),
                edge           = round(edge, 4),
                asset          = asset,
                current_price  = spot,
                threshold_price= threshold,
                direction      = direction,
                hours_to_close = market.hours_to_resolution,
                volume_usd     = market.volume_usd,
            ))

        opportunities.sort(key=lambda x: x.edge, reverse=True)
        logger.info(
            f"Velocity scan: {len(candidates)} crypto markets → "
            f"{len(opportunities)} opportunities "
            f"(min_edge={self.min_edge:.0%}, prices={list(prices.keys())})"
        )
        return opportunities
