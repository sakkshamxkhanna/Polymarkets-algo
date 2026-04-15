"""
WebSocket feed for real-time Polymarket CLOB orderbook data.
Handles book (full snapshot) and price_change (delta) events.
"""
import asyncio
import json
import logging
import time
from decimal import Decimal

import websockets
from websockets.exceptions import ConnectionClosed

from .normalization import OrderbookSnapshot, PriceLevel

logger = logging.getLogger(__name__)


class WebSocketBookFeed:
    def __init__(self, ws_host: str):
        self.ws_host = ws_host
        # token_id -> OrderbookSnapshot (live in-memory state)
        self.books: dict[str, OrderbookSnapshot] = {}
        self._subscribed_tokens: set[str] = set()
        self._ws = None
        self._running = False
        self._last_message_ts: float = 0.0

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not getattr(self._ws, "closed", False)

    @property
    def ws_gap_seconds(self) -> float:
        if self._last_message_ts == 0:
            return 0.0  # never received a message — return 0 so kill switch skips check
        return time.time() - self._last_message_ts

    async def subscribe(self, token_ids: list[str]):
        """Add token IDs to subscription list."""
        for tid in token_ids:
            self._subscribed_tokens.add(tid)
        if self._ws:
            try:
                await self._send_subscribe(self._ws, token_ids)
            except Exception:
                pass  # will re-subscribe on next reconnect

    async def _send_subscribe(self, ws, token_ids: list[str]):
        for token_id in token_ids:
            msg = json.dumps({
                "type": "subscribe",
                "channel": "book",
                "market": token_id,
            })
            await ws.send(msg)

    def _apply_book_snapshot(self, data: dict):
        token_id = data.get("market", data.get("asset_id", ""))
        bids = [
            PriceLevel(price=Decimal(str(b["price"])), size=Decimal(str(b["size"])))
            for b in data.get("bids", [])
        ]
        asks = [
            PriceLevel(price=Decimal(str(a["price"])), size=Decimal(str(a["size"])))
            for a in data.get("asks", [])
        ]
        self.books[token_id] = OrderbookSnapshot(
            token_id=token_id,
            timestamp=time.time(),
            bids=sorted(bids, key=lambda x: x.price, reverse=True),
            asks=sorted(asks, key=lambda x: x.price),
        )

    def _apply_price_change(self, data: dict):
        """Apply incremental delta update."""
        token_id = data.get("market", data.get("asset_id", ""))
        if token_id not in self.books:
            return

        book = self.books[token_id]
        side = data.get("side", "").lower()
        price = Decimal(str(data.get("price", "0")))
        new_size = Decimal(str(data.get("size", "0")))

        if side == "bid":
            levels = book.bids
            reverse = True
        else:
            levels = book.asks
            reverse = False

        # Remove existing level at this price
        levels[:] = [l for l in levels if l.price != price]

        # Add new level if size > 0
        if new_size > 0:
            levels.append(PriceLevel(price=price, size=new_size))
            levels.sort(key=lambda x: x.price, reverse=reverse)

        book.timestamp = time.time()

    async def run(self):
        """Main loop — connects and reconnects with backoff."""
        self._running = True
        backoff = 1.0
        while self._running:
            try:
                logger.info(f"Connecting to Polymarket WebSocket: {self.ws_host}")
                async with websockets.connect(
                    self.ws_host,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    backoff = 1.0
                    logger.info("WebSocket connected. Subscribing to tokens...")
                    if self._subscribed_tokens:
                        await self._send_subscribe(ws, list(self._subscribed_tokens))

                    async for raw_msg in ws:
                        self._last_message_ts = time.time()
                        try:
                            data = json.loads(raw_msg)
                            event_type = data.get("event_type", data.get("type", ""))
                            if event_type == "book":
                                self._apply_book_snapshot(data)
                            elif event_type == "price_change":
                                self._apply_price_change(data)
                        except Exception as e:
                            logger.debug(f"WS message parse error: {e}")

            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}. Reconnecting in {backoff}s...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in {backoff}s...")
            finally:
                self._ws = None

            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
