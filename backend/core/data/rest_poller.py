"""
REST poller for Polymarket CLOB + Gamma API market data.
Rate limit budget: 8 req/10s (leaves 2/s buffer for execution).
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from .normalization import Market, normalize_gamma_market

logger = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 1.25  # seconds between poll batches


class RESTPoller:
    def __init__(self, gamma_host: str, clob_host: str):
        self.gamma_host = gamma_host
        self.clob_host = clob_host
        self._markets: dict[str, Market] = {}
        self._last_poll: float = 0.0
        self._running = False
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def markets(self) -> list[Market]:
        return list(self._markets.values())

    async def _fetch_markets_page(
        self,
        client: httpx.AsyncClient,
        offset: int = 0,
        extra_params: Optional[dict] = None,
    ) -> list[dict]:
        try:
            params: dict = {"active": "true", "closed": "false", "limit": 100, "offset": offset}
            if extra_params:
                params.update(extra_params)
            resp = await client.get(
                f"{self.gamma_host}/markets",
                params=params,
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("markets", data.get("data", []))
            logger.warning(f"Gamma API returned {resp.status_code}")
            return []
        except Exception as e:
            logger.error(f"Gamma API fetch error: {e}")
            return []

    async def _fetch_near_resolution(self, client: httpx.AsyncClient) -> list[dict]:
        """
        Dedicated pass: fetch markets sorted by end_date ascending so that
        markets closing in the next 48h are captured even if they don't rank
        in the top 300 by volume.

        Velocity Momentum strategy requires these to generate signals.
        """
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        end_max = now + timedelta(hours=72)  # 72h to get a buffer above 48h

        try:
            resp = await client.get(
                f"{self.gamma_host}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 100,
                    "order": "endDate",
                    "ascending": "true",
                    "end_date_max": end_max.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = data if isinstance(data, list) else data.get("markets", data.get("data", []))
                logger.info(f"Near-resolution fetch: {len(result)} markets closing within 72h")
                return result
        except Exception as e:
            logger.warning(f"Near-resolution fetch failed: {e}")
        return []

    async def _poll_once(self, client: httpx.AsyncClient):
        """Fetch active markets from Gamma API — top 300 by default + near-resolution."""
        all_raw: list[dict] = []

        # Pass 1: top 300 active markets (by Gamma default order = volume)
        for offset in range(0, 300, 100):
            batch = await self._fetch_markets_page(client, offset)
            all_raw.extend(batch)
            if len(batch) < 100:
                break
            await asyncio.sleep(RATE_LIMIT_DELAY)

        # Pass 2: near-resolution markets (sorted by endDate asc, within 72h)
        # These power the Velocity Momentum strategy and may not appear in Pass 1.
        near_res = await self._fetch_near_resolution(client)
        all_raw.extend(near_res)

        new_markets: dict[str, Market] = {}
        for raw in all_raw:
            market = normalize_gamma_market(raw)
            if market and market.is_active:
                new_markets[market.condition_id] = market

        self._markets = new_markets
        self._last_poll = time.time()
        logger.info(f"Polled {len(self._markets)} active markets ({len(near_res)} near-resolution)")

    async def run(self):
        """Poll markets every 60 seconds."""
        self._running = True
        async with httpx.AsyncClient() as client:
            self._client = client
            while self._running:
                try:
                    await self._poll_once(client)
                except Exception as e:
                    logger.error(f"REST poll error: {e}")
                await asyncio.sleep(60.0)

    async def stop(self):
        self._running = False

    def get_market(self, condition_id: str) -> Optional[Market]:
        return self._markets.get(condition_id)
