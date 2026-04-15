"""
Matching engine simulator with price-time priority and queue position tracking.

Critical audit fix: the original system was "queue position blind" — it would
fill at the back of the queue ~100% of the time on adverse events.
This simulator tracks queue position and flags adverse fills correctly.
"""
import uuid
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class SimOrder:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token_id: str = ""
    side: str = "BUY"  # BUY or SELL
    price: Decimal = Decimal("0")
    size: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    queue_pos: int = 0

    def __post_init__(self):
        if self.remaining == Decimal("0"):
            self.remaining = self.size


@dataclass
class SimFill:
    order_id: str
    price: Decimal
    size: Decimal
    is_adverse: bool  # True = informed trader hit us (bad fill)


class MatchingSimulator:
    """
    Price-time priority queue simulator.
    Each price level maintains a deque of orders in time order.
    """

    def __init__(self):
        # token_id -> {price -> deque[SimOrder]}
        self.queues: dict[str, dict[Decimal, deque[SimOrder]]] = {}
        self._prev_sizes: dict[tuple, Decimal] = {}  # (token_id, price) -> last known size

    def submit(self, order: SimOrder) -> str:
        if order.token_id not in self.queues:
            self.queues[order.token_id] = {}

        levels = self.queues[order.token_id]
        if order.price not in levels:
            levels[order.price] = deque()

        order.queue_pos = len(levels[order.price])
        levels[order.price].append(order)
        return order.id

    def cancel(self, token_id: str, order_id: str):
        levels = self.queues.get(token_id, {})
        for price, queue in levels.items():
            for i, o in enumerate(queue):
                if o.id == order_id:
                    del queue[i]
                    return

    def on_book_delta(
        self,
        token_id: str,
        price: Decimal,
        new_size: Decimal,
        side: str,
    ) -> list[SimFill]:
        """
        Called when a book level changes.
        If new_size == 0, the level was consumed — fill orders in queue order.
        Flags adverse fills: if bid was consumed and we're a buyer, informed seller hit us.
        """
        key = (token_id, price)
        prev_size = self._prev_sizes.get(key, new_size)
        self._prev_sizes[key] = new_size

        fills: list[SimFill] = []

        if new_size == 0:
            # Level consumed entirely — fill orders at this price
            levels = self.queues.get(token_id, {})
            queue = levels.get(price, deque())
            while queue:
                o = queue.popleft()
                fill_size = min(o.remaining, prev_size)
                is_adverse = self._is_adverse(o, side)
                fills.append(SimFill(
                    order_id=o.id,
                    price=price,
                    size=fill_size,
                    is_adverse=is_adverse,
                ))
                o.remaining -= fill_size
                if o.remaining > 0:
                    queue.appendleft(o)  # partial fill
                    break
        elif new_size < prev_size:
            # Partial consumption — update queue positions
            consumed = prev_size - new_size
            levels = self.queues.get(token_id, {})
            queue = levels.get(price, deque())
            remaining_consumption = consumed
            for o in list(queue):
                if remaining_consumption <= 0:
                    break
                fill_size = min(o.remaining, remaining_consumption)
                is_adverse = self._is_adverse(o, side)
                fills.append(SimFill(
                    order_id=o.id,
                    price=price,
                    size=fill_size,
                    is_adverse=is_adverse,
                ))
                o.remaining -= fill_size
                remaining_consumption -= fill_size
                if o.remaining == 0:
                    queue.popleft()

        return fills

    def _is_adverse(self, order: SimOrder, delta_side: str) -> bool:
        """
        Flag as adverse: bid consumed + we are buyer → informed seller hit us.
        This is the textbook adverse selection scenario in prediction markets.
        """
        return order.side == "BUY" and delta_side.lower() == "bid"
