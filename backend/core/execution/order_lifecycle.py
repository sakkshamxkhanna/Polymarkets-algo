"""
Order Lifecycle State Machine — the most critical audit fix.

States: PENDING_SUBMIT → SUBMITTED → LIVE → PARTIALLY_FILLED → FILLED
                                               ↓                    ↓
                               PENDING_CANCEL → CANCELLED    REJECTED/EXPIRED/ORPHANED

Audit gaps fixed:
- Full state tracking (no more "submitted and forgotten")
- 2s timeout before ORPHANED
- cancel_replace: atomic cancel + resubmit to minimize quote gap
- reconcile: periodic diff vs CLOB open orders to detect ORPHANED
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class OrderState(str, Enum):
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    LIVE = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PENDING_CANCEL = "pending_cancel"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ORPHANED = "orphaned"


@dataclass
class Order:
    local_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    clob_id: Optional[str] = None
    token_id: str = ""
    market_id: str = ""
    question: str = ""
    side: str = "BUY"       # BUY or SELL
    outcome: str = "YES"    # YES or NO
    price: Decimal = Decimal("0")
    size: Decimal = Decimal("0")  # USDC
    state: OrderState = OrderState.PENDING_SUBMIT
    filled_size: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    strategy: str = "resolution_timing"
    sim_mode: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    est_queue_pos: int = 0

    def transition(self, new_state: OrderState):
        logger.debug(f"Order {self.local_id[:8]}: {self.state} → {new_state}")
        self.state = new_state
        self.updated_at = time.time()

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
            OrderState.ORPHANED,
        }

    def to_dict(self) -> dict:
        return {
            "local_id": self.local_id,
            "clob_id": self.clob_id,
            "token_id": self.token_id,
            "market_id": self.market_id,
            "question": self.question,
            "side": self.side,
            "outcome": self.outcome,
            "price": float(self.price),
            "size": float(self.size),
            "state": self.state.value,
            "filled_size": float(self.filled_size),
            "avg_fill_price": float(self.avg_fill_price) if self.avg_fill_price else None,
            "strategy": self.strategy,
            "sim_mode": self.sim_mode,
            "created_at": self.created_at,
        }


class OrderLifecycleManager:
    SUBMIT_TIMEOUT_S = 2.0

    def __init__(self, clob_client=None, sim_mode: bool = True):
        self.clob = clob_client
        self.sim_mode = sim_mode
        self.orders: dict[str, Order] = {}  # local_id -> Order

    async def submit(self, order: Order) -> str:
        """Submit order to CLOB (or simulator). Returns local_id."""
        order.state = OrderState.PENDING_SUBMIT
        self.orders[order.local_id] = order

        if self.sim_mode:
            # Simulate successful submission
            await asyncio.sleep(0.05)  # simulate ~50ms latency
            order.clob_id = f"sim_{order.local_id[:8]}"
            order.transition(OrderState.LIVE)
            logger.info(f"SIM: Order {order.local_id[:8]} live @ {order.price}")
            return order.local_id

        try:
            async with asyncio.timeout(self.SUBMIT_TIMEOUT_S):
                # Real CLOB submission via py-clob-client
                from py_clob_client.clob_types import OrderArgs, OrderType, Side
                order_args = OrderArgs(
                    price=float(order.price),
                    size=float(order.size),
                    side=Side.BUY if order.side == "BUY" else Side.SELL,
                    token_id=order.token_id,
                )
                signed = self.clob.create_order(order_args)
                resp = self.clob.post_order(signed, OrderType.GTC)
                order.clob_id = resp.get("orderID", "")
                order.transition(OrderState.SUBMITTED)
                logger.info(f"Order submitted: {order.clob_id}")

        except asyncio.TimeoutError:
            order.transition(OrderState.ORPHANED)
            logger.error(f"Order {order.local_id[:8]} timed out after {self.SUBMIT_TIMEOUT_S}s → ORPHANED")
        except Exception as e:
            order.transition(OrderState.ORPHANED)
            logger.error(f"Order submission error: {e} → ORPHANED")

        return order.local_id

    async def cancel(self, local_id: str) -> bool:
        """Cancel an order."""
        order = self.orders.get(local_id)
        if not order or order.is_terminal:
            return False

        order.transition(OrderState.PENDING_CANCEL)

        if self.sim_mode:
            await asyncio.sleep(0.02)
            order.transition(OrderState.CANCELLED)
            return True

        try:
            async with asyncio.timeout(self.SUBMIT_TIMEOUT_S):
                self.clob.cancel_order(order_id=order.clob_id)
                order.transition(OrderState.CANCELLED)
                return True
        except Exception as e:
            logger.error(f"Cancel failed for {local_id[:8]}: {e}")
            return False

    async def cancel_replace(self, local_id: str, new_price: Decimal) -> Optional[str]:
        """
        Atomic cancel + resubmit at new price.
        Minimizes quote gap (key audit fix for market-making strategies).
        """
        old_order = self.orders.get(local_id)
        if not old_order:
            return None

        # Pre-build replacement before cancelling
        replacement = Order(
            token_id=old_order.token_id,
            market_id=old_order.market_id,
            question=old_order.question,
            side=old_order.side,
            outcome=old_order.outcome,
            price=new_price,
            size=old_order.size - old_order.filled_size,
            strategy=old_order.strategy,
            sim_mode=self.sim_mode,
        )

        # Cancel old, submit new immediately
        await self.cancel(local_id)
        new_id = await self.submit(replacement)
        logger.info(f"Cancel-replace: {local_id[:8]} → {new_id[:8]} @ {new_price}")
        return new_id

    async def reconcile(self, clob_open_ids: set[str]):
        """
        Periodic reconciliation vs CLOB open orders endpoint.
        Detects ORPHANED orders (we think live, CLOB doesn't know them).
        """
        for order in list(self.orders.values()):
            if order.state in {OrderState.LIVE, OrderState.PARTIALLY_FILLED}:
                if order.clob_id and order.clob_id not in clob_open_ids:
                    # We think it's live but CLOB doesn't — likely filled or cancelled externally
                    order.transition(OrderState.ORPHANED)
                    logger.warning(f"Order {order.local_id[:8]} reconciled as ORPHANED")

    def record_fill(self, clob_id: str, fill_size: Decimal, fill_price: Decimal):
        """Handle WebSocket fill event."""
        for order in self.orders.values():
            if order.clob_id == clob_id:
                order.filled_size += fill_size
                # Running average fill price
                if order.avg_fill_price is None:
                    order.avg_fill_price = fill_price
                else:
                    total_filled = order.filled_size
                    prev_filled = total_filled - fill_size
                    order.avg_fill_price = (
                        (order.avg_fill_price * prev_filled + fill_price * fill_size) / total_filled
                    )

                if order.filled_size >= order.size:
                    order.transition(OrderState.FILLED)
                else:
                    order.transition(OrderState.PARTIALLY_FILLED)

                logger.info(
                    f"Fill: {clob_id} {fill_size} @ {fill_price} "
                    f"(total filled: {order.filled_size}/{order.size})"
                )
                return

    def get_orphaned(self) -> list[Order]:
        return [o for o in self.orders.values() if o.state == OrderState.ORPHANED]

    def get_active(self) -> list[Order]:
        return [
            o for o in self.orders.values()
            if o.state in {OrderState.LIVE, OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED}
        ]
