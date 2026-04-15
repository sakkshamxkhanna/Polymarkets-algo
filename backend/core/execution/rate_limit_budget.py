"""
Rate limit token bucket manager.
10 req/s shared across all operations — allocated by priority.

Audit fix: a bot managing 10 markets burns rate limit on order mgmt alone
if it doesn't budget explicitly.
"""
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

BUDGETS = {
    "emergency_cancel": 4.0,   # req/s — reserved for kill switch
    "fill_confirmation": 2.0,  # WebSocket-based, REST fallback
    "order_submit": 2.0,       # max 2 new orders/sec
    "book_polling": 1.5,       # REST fallback when WS drops
    "position_query": 0.5,     # low priority
}


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> float:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            # Need to wait
            deficit = tokens - self._tokens
            wait_time = deficit / self.rate
            return wait_time


class RateLimitBudget:
    """10 req/s total, allocated by operation priority."""

    def __init__(self, total_rps: float = 10.0):
        self._buckets = {
            op: TokenBucket(rate=rate, capacity=max(rate * 2, 1.0))
            for op, rate in BUDGETS.items()
        }

    async def acquire(self, operation: str) -> bool:
        """
        Acquire budget for operation. Returns True immediately if available,
        blocks briefly if over limit.
        """
        bucket = self._buckets.get(operation)
        if not bucket:
            logger.warning(f"Unknown operation '{operation}' — using default budget")
            bucket = self._buckets["position_query"]

        wait = await bucket.acquire()
        if wait > 0:
            logger.debug(f"Rate limit: {operation} waiting {wait:.3f}s")
            await asyncio.sleep(wait)
        return True
