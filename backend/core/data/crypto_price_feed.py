"""
Real-time crypto price feed backed by CoinGecko's free public API.

Results are cached for CACHE_TTL seconds to avoid hammering the rate limit
(CoinGecko free tier: ~30 req/min).  A stale cache is returned rather than
raising — callers must tolerate None for unknown symbols.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL = 30          # seconds between CoinGecko refreshes
REQUEST_TIMEOUT = 6.0   # seconds

# Map Polymarket-parsed symbol → CoinGecko ID
COINGECKO_IDS: dict[str, str] = {
    "BTC":   "bitcoin",
    "ETH":   "ethereum",
    "SOL":   "solana",
    "BNB":   "binancecoin",
    "XRP":   "ripple",
    "DOGE":  "dogecoin",
    "MATIC": "matic-network",
    "AVAX":  "avalanche-2",
    "LINK":  "chainlink",
    "UNI":   "uniswap",
    "ADA":   "cardano",
    "DOT":   "polkadot",
    "LTC":   "litecoin",
    "BCH":   "bitcoin-cash",
    "ATOM":  "cosmos",
    "NEAR":  "near",
    "APT":   "aptos",
    "SUI":   "sui",
    "ARB":   "arbitrum",
    "OP":    "optimism",
}


class CryptoPriceFeed:
    """
    Async, cached wrapper around the CoinGecko /simple/price endpoint.

    Usage:
        feed = CryptoPriceFeed()
        prices = await feed.get_prices(["BTC", "ETH"])
        btc_usd = prices.get("BTC")   # float or None
    """

    def __init__(self):
        # {symbol: (price_usd, fetched_at_unix)}
        self._cache: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def get_prices(self, symbols: list[str]) -> dict[str, Optional[float]]:
        """
        Return {symbol: usd_price} for every symbol in the list.
        Symbols not found in CoinGecko are omitted from the result.
        """
        now = time.monotonic()

        # Which symbols need a fresh fetch?
        stale = [
            s for s in symbols
            if s in COINGECKO_IDS
            and (s not in self._cache or now - self._cache[s][1] > CACHE_TTL)
        ]

        if stale:
            async with self._lock:
                # Re-check after acquiring lock (another coroutine may have fetched)
                stale = [
                    s for s in stale
                    if s not in self._cache or now - self._cache[s][1] > CACHE_TTL
                ]
                if stale:
                    await self._fetch(stale)

        return {s: self._cache[s][0] for s in symbols if s in self._cache}

    async def get_price(self, symbol: str) -> Optional[float]:
        """Convenience method for a single symbol."""
        result = await self.get_prices([symbol])
        return result.get(symbol)

    async def _fetch(self, symbols: list[str]) -> None:
        """Fetch prices from CoinGecko and update cache. Called inside lock."""
        ids = ",".join(COINGECKO_IDS[s] for s in symbols if s in COINGECKO_IDS)
        if not ids:
            return

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": ids, "vs_currencies": "usd"}

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data: dict = resp.json()

            now = time.monotonic()
            fetched = 0
            for sym in symbols:
                cg_id = COINGECKO_IDS.get(sym)
                if cg_id and cg_id in data and "usd" in data[cg_id]:
                    price = float(data[cg_id]["usd"])
                    self._cache[sym] = (price, now)
                    fetched += 1

            logger.debug(f"CoinGecko: fetched {fetched}/{len(symbols)} prices")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("CoinGecko rate limit hit — using cached prices")
            else:
                logger.error(f"CoinGecko HTTP error {e.response.status_code}: {e}")
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e} — using cached prices")
