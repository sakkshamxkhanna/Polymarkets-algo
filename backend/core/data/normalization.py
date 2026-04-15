from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional


@dataclass
class PriceLevel:
    price: Decimal
    size: Decimal


@dataclass
class OrderbookSnapshot:
    token_id: str
    timestamp: float
    bids: list[PriceLevel] = field(default_factory=list)  # sorted best-first (highest bid first)
    asks: list[PriceLevel] = field(default_factory=list)  # sorted best-first (lowest ask first)

    @property
    def best_bid(self) -> Optional[Decimal]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[Decimal]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[Decimal]:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread_cents(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return float((self.best_ask - self.best_bid) * 100)
        return None


@dataclass
class Market:
    condition_id: str
    question: str
    end_date: datetime
    volume_usd: float
    yes_token_id: str
    no_token_id: str
    resolution_criteria: str
    category: str = ""
    tags: list[str] = field(default_factory=list)
    spread_cents: float = 0.0
    mid_price: float = 0.5
    best_bid: float = 0.0   # from Gamma API — fallback when WS book not yet subscribed
    best_ask: float = 1.0   # from Gamma API — fallback when WS book not yet subscribed
    is_active: bool = True
    oracle_submitted: bool = False  # UMA assertion already submitted

    @property
    def hours_to_resolution(self) -> float:
        now = datetime.utcnow()
        delta = self.end_date - now
        return max(0.0, delta.total_seconds() / 3600)

    @property
    def is_near_resolution(self) -> bool:
        return self.hours_to_resolution < 6.0


_SPORTS_KW = {"nfl","nba","nhl","mlb","mls","ufc","fifa","league","cup","championship",
              "team","player","season","game","match","win","finals","playoff","draft",
              "quarterback","touchdown","goal","basketball","football","baseball","hockey",
              "tennis","golf","soccer","olympics","wrestling","boxing","formula","f1","gp"}
_CRYPTO_KW = {"bitcoin","btc","eth","ethereum","crypto","defi","token","blockchain",
              "solana","sol","xrp","dogecoin","doge","usdc","nft","altcoin","binance",
              "coinbase","price","memecoin","stablecoin"}
_ECON_KW   = {"fed","gdp","inflation","recession","interest rate","rate cut","rate hike",
              "unemployment","cpi","fomc","tariff","trade war","economic","stock market",
              "s&p","nasdaq","dow jones","treasury","yield","ipo","earnings"}
_POL_KW    = {"president","election","congress","senate","vote","democrat","republican",
              "trump","biden","harris","governor","prime minister","parliament","policy",
              "law","bill","supreme court","impeach","cabinet","minister","geopolit"}


def _infer_category(question: str, tags: list) -> str:
    """Infer market category from question text and tags."""
    q = question.lower()
    tag_str = " ".join(str(t).lower() for t in tags)
    combined = q + " " + tag_str
    words = set(combined.split())

    if words & _CRYPTO_KW:
        return "crypto"
    if words & _SPORTS_KW:
        return "sports"
    if words & _ECON_KW:
        return "economics"
    if words & _POL_KW:
        return "politics"
    return "politics"  # most markets are political by default


def normalize_gamma_market(raw: dict) -> Optional[Market]:
    """Convert Gamma API market response to typed Market."""
    import json as _json
    try:
        tokens = raw.get("tokens", [])
        if not tokens:
            clob_ids = raw.get("clobTokenIds", "[]")
            if isinstance(clob_ids, str):
                try:
                    tokens = _json.loads(clob_ids)
                except Exception:
                    tokens = []
            elif isinstance(clob_ids, list):
                tokens = clob_ids
        if isinstance(tokens, list) and len(tokens) >= 2:
            if isinstance(tokens[0], dict):
                yes_token = tokens[0].get("token_id", "")
                no_token = tokens[1].get("token_id", "")
            else:
                yes_token = tokens[0]
                no_token = tokens[1]
        else:
            return None

        end_date_str = raw.get("endDate") or raw.get("end_date_iso", "")
        try:
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                end_date = end_date.replace(tzinfo=None)
            else:
                return None
        except ValueError:
            return None

        # Derive mid_price and spread from live bid/ask if available
        best_bid = float(raw.get("bestBid") or 0)
        best_ask = float(raw.get("bestAsk") or 0)
        last_price = float(raw.get("lastTradePrice") or 0)
        if best_bid > 0 and best_ask > 0:
            mid_price = (best_bid + best_ask) / 2
            spread_cents = round((best_ask - best_bid) * 100, 2)
        elif last_price > 0:
            mid_price = last_price
            spread_cents = 0.0
        else:
            mid_price = 0.5
            spread_cents = 0.0

        return Market(
            condition_id=raw.get("conditionId", raw.get("condition_id", "")),
            question=raw.get("question", raw.get("title", "")),
            end_date=end_date,
            volume_usd=float(raw.get("volume", 0)),
            yes_token_id=yes_token,
            no_token_id=no_token,
            resolution_criteria=raw.get("resolutionCriteria", raw.get("description", "")),
            category=_infer_category(raw.get("question", ""), raw.get("tags", [])),
            tags=raw.get("tags", []),
            mid_price=mid_price,
            spread_cents=spread_cents,
            best_bid=best_bid,
            best_ask=best_ask if best_ask > 0 else 1.0,
            is_active=raw.get("active", True) and not raw.get("closed", False),
            # oracle_submitted = True once Polymarket closes the book after UMA settlement
            # resolvedBy is just the resolver contract address (set at creation) — not a signal
            oracle_submitted=raw.get("closed", False) or not raw.get("acceptingOrders", True),
        )
    except Exception:
        return None


def normalize_clob_orderbook(raw: dict) -> Optional[OrderbookSnapshot]:
    """Convert CLOB API orderbook response to typed OrderbookSnapshot."""
    try:
        token_id = raw.get("asset_id", "")
        bids = [
            PriceLevel(price=Decimal(str(b["price"])), size=Decimal(str(b["size"])))
            for b in raw.get("bids", [])
        ]
        asks = [
            PriceLevel(price=Decimal(str(a["price"])), size=Decimal(str(a["size"])))
            for a in raw.get("asks", [])
        ]
        return OrderbookSnapshot(
            token_id=token_id,
            timestamp=__import__("time").time(),
            bids=sorted(bids, key=lambda x: x.price, reverse=True),
            asks=sorted(asks, key=lambda x: x.price),
        )
    except Exception:
        return None
