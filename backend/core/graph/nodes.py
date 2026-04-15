"""
LangGraph node functions — each node transforms TradingState and returns updated TradingState.
Nodes are pure async functions: (state: TradingState) -> TradingState (partial update).
"""
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

from .state import TradingState

logger = logging.getLogger(__name__)


async def data_node(state: TradingState, *, rest_poller, ws_feed) -> dict:
    """Layer 1: Fetch current markets and orderbook snapshots."""
    start = time.monotonic()
    markets = rest_poller.markets

    # Serialize markets for state transport
    markets_dicts = []
    for m in markets:
        markets_dicts.append({
            "condition_id": m.condition_id,
            "question": m.question,
            "end_date": m.end_date.isoformat(),
            "volume_usd": m.volume_usd,
            "yes_token_id": m.yes_token_id,
            "no_token_id": m.no_token_id,
            "resolution_criteria": m.resolution_criteria,
            "category": m.category,
            "is_active": m.is_active,
            "oracle_submitted": m.oracle_submitted,
            "hours_to_resolution": m.hours_to_resolution,
            "mid_price": m.mid_price,
            "spread_cents": m.spread_cents,
            "best_bid": m.best_bid,
            "best_ask": m.best_ask,
        })

    # Serialize orderbooks
    orderbooks_dicts = {}
    for token_id, book in ws_feed.books.items():
        orderbooks_dicts[token_id] = {
            "token_id": token_id,
            "timestamp": book.timestamp,
            "best_bid": float(book.best_bid) if book.best_bid else None,
            "best_ask": float(book.best_ask) if book.best_ask else None,
            "mid_price": float(book.mid_price) if book.mid_price else None,
            "spread_cents": book.spread_cents,
            "bids": [{"price": float(b.price), "size": float(b.size)} for b in book.bids[:10]],
            "asks": [{"price": float(a.price), "size": float(a.size)} for a in book.asks[:10]],
        }

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.debug(f"Data node: {len(markets_dicts)} markets, {len(orderbooks_dicts)} orderbooks in {elapsed_ms:.0f}ms")

    return {
        "markets": markets_dicts,
        "orderbooks": orderbooks_dicts,
        "ws_gap_seconds": ws_feed.ws_gap_seconds,
        "api_latency_ms": elapsed_ms,
    }


async def signal_node(state: TradingState, *, oracle_monitor, source_verifier, fair_value_engine, velocity_scanner=None) -> dict:
    """Layer 2: Scan for opportunities and verify them."""
    from core.data.normalization import Market
    from datetime import datetime as dt

    # Reconstruct Market objects from serialized state
    markets = []
    for m_dict in state.get("markets", []):
        try:
            end_date = dt.fromisoformat(m_dict["end_date"].replace("Z", ""))
            m = Market(
                condition_id=m_dict["condition_id"],
                question=m_dict["question"],
                end_date=end_date,
                volume_usd=m_dict["volume_usd"],
                yes_token_id=m_dict["yes_token_id"],
                no_token_id=m_dict["no_token_id"],
                resolution_criteria=m_dict.get("resolution_criteria", ""),
                category=m_dict.get("category", ""),
                is_active=m_dict.get("is_active", True),
                oracle_submitted=m_dict.get("oracle_submitted", False),
                best_bid=m_dict.get("best_bid", 0.0),
                best_ask=m_dict.get("best_ask", 1.0),
                mid_price=m_dict.get("mid_price", 0.5),
                spread_cents=m_dict.get("spread_cents", 0.0),
            )
            markets.append(m)
        except Exception as e:
            logger.debug(f"Skip market: {e}")

    # Reconstruct orderbooks
    from core.data.normalization import OrderbookSnapshot, PriceLevel
    orderbooks = {}
    for tid, book_dict in state.get("orderbooks", {}).items():
        bids = [PriceLevel(Decimal(str(b["price"])), Decimal(str(b["size"]))) for b in book_dict.get("bids", [])]
        asks = [PriceLevel(Decimal(str(a["price"])), Decimal(str(a["size"]))) for a in book_dict.get("asks", [])]
        orderbooks[tid] = OrderbookSnapshot(
            token_id=tid,
            timestamp=book_dict.get("timestamp", time.time()),
            bids=bids,
            asks=asks,
        )

    pnl = state.get("pnl_snapshot", {})
    total_capital = pnl.get("total_capital", 500.0)
    current_notional = pnl.get("total_notional", 0.0)

    # Respect per-strategy enable/disable flag (set via /api/strategy/{name}/toggle)
    strategy_enabled = state.get("strategy_enabled", {"resolution_timing": True})
    oracle_lag_enabled = strategy_enabled.get("resolution_timing", True)

    raw_opportunities = (
        oracle_monitor.scan(markets, orderbooks, total_capital, current_notional)
        if oracle_lag_enabled
        else []
    )
    if not oracle_lag_enabled:
        logger.info("Oracle lag strategy disabled — skipping oracle_monitor.scan()")

    verified = []
    for opp in raw_opportunities:
        result = source_verifier.verify(opp.market, opp.side)
        if not result.confirmed:
            continue

        # Apply oracle risk discount
        fair_value = fair_value_engine.compute_fair_value(
            Decimal("1.00"), result.category
        )
        net_edge = fair_value_engine.net_edge_cents(opp.entry_price, fair_value)
        if net_edge < 3.0:  # net edge must exceed 3¢ after oracle risk buffer
            continue

        verified.append({
            "market_id": opp.market.condition_id,
            "question": opp.market.question,
            "token_id": opp.token_id,
            "side": opp.side,
            "entry_price": float(opp.entry_price),
            "fair_value": float(fair_value),
            "gross_edge_cents": opp.gross_edge_cents,
            "net_edge_cents": net_edge,
            "hours_to_resolution": opp.hours_to_resolution,
            "confidence": result.confidence,
            "category": result.category,
            "sources": result.sources,
            "reason": result.reason,
        })

    # ── Velocity Momentum signals (active markets, real-time crypto prices) ──
    velocity_verified: list[dict] = []
    if velocity_scanner is not None:
        try:
            vm_opps = await velocity_scanner.scan(markets, total_capital, current_notional)
            for opp in vm_opps:
                # Active markets resolve normally (not via stalled UMA oracle)
                # → use Category-A oracle risk buffer (0.5%)
                fair_value = fair_value_engine.compute_fair_value(Decimal("1.00"), "A")
                net_edge = fair_value_engine.net_edge_cents(opp.entry_price, fair_value)
                if net_edge < 3.0:
                    continue
                velocity_verified.append({
                    "market_id":         opp.market_id,
                    "question":          opp.question,
                    "token_id":          opp.token_id,
                    "side":              opp.side,
                    "entry_price":       float(opp.entry_price),
                    "fair_value":        float(fair_value),
                    "gross_edge_cents":  float((Decimal("1.00") - opp.entry_price) * 100),
                    "net_edge_cents":    net_edge,
                    "hours_to_resolution": opp.hours_to_close,
                    "confidence":        opp.implied_prob,
                    "category":          "A",
                    "sources":           [
                        f"{opp.asset}@${opp.current_price:,.0f}",
                        f"threshold=${opp.threshold_price:,.0f}",
                        f"model_edge={opp.edge:.0%}",
                    ],
                    "reason": (
                        f"Velocity: {opp.asset} {opp.direction} "
                        f"${opp.threshold_price:,.0f} "
                        f"(spot=${opp.current_price:,.0f}), "
                        f"implied={opp.implied_prob:.0%}, "
                        f"market={float(opp.entry_price):.0%}, "
                        f"edge={opp.edge:.0%}"
                    ),
                    "strategy":          "velocity_momentum",
                    "exit_target":       opp.exit_target,
                    "stop_price":        opp.stop_price,
                })
        except Exception as e:
            logger.error(f"Velocity scanner error: {e}", exc_info=True)

    all_verified = verified + velocity_verified
    logger.info(
        f"Signal: {len(raw_opportunities)} oracle-lag raw → {len(verified)} verified "
        f"+ {len(velocity_verified)} velocity = {len(all_verified)} total"
    )

    return {
        "raw_opportunities": [
            {"market_id": o.market.condition_id, "side": o.side, "gross_edge_cents": o.gross_edge_cents}
            for o in raw_opportunities
        ],
        "verified_opportunities": all_verified,
    }


async def risk_node(state: TradingState, *, kill_switch, position_ledger, capital_sizer) -> dict:
    """Layer 3: Risk evaluation and position sizing."""

    # Check kill switch first
    if kill_switch.is_active:
        return {
            "risk_decision": "VETOED",
            "risk_reason": f"Kill switch active: {kill_switch.fire_reason}",
            "approved_orders": [],
            "kill_switch_active": True,
        }

    # Evaluate kill switch triggers
    ws_gap = state.get("ws_gap_seconds", 0.0)
    daily_pnl = state.get("pnl_snapshot", {}).get("daily_pnl", 0.0)
    total_capital = state.get("pnl_snapshot", {}).get("total_capital", 500.0)
    daily_drawdown_pct = abs(min(0.0, daily_pnl)) / max(total_capital, 1.0)
    orphaned = bool(state.get("orphaned_order_ids", []))

    trigger = kill_switch.evaluate(
        ws_last_msg_ts=time.time() - ws_gap,
        daily_drawdown_pct=daily_drawdown_pct,
        has_orphaned_orders=orphaned,
    )
    if trigger:
        await kill_switch.fire(trigger)
        return {
            "risk_decision": "VETOED",
            "risk_reason": f"Kill switch triggered: {trigger}",
            "approved_orders": [],
            "kill_switch_active": True,
            "system_alerts": [{
                "type": "KILL_SWITCH",
                "message": f"Kill switch fired: {trigger}",
                "severity": "critical",
                "timestamp": time.time(),
            }],
        }

    # ── Deduplication: one trade per market, highest market confidence wins ──
    # Sort by entry_price descending: higher price = market is more confident
    # in that outcome. This correctly picks NO@93¢ over YES@7¢ for the same
    # market, rather than the phantom gross-edge of the cheap/unlikely side.
    opps_sorted = sorted(
        state.get("verified_opportunities", []),
        key=lambda o: o["entry_price"],
        reverse=True,
    )
    seen_markets: set[str] = set()
    deduped_opps = []
    for opp in opps_sorted:
        mid = opp["market_id"]
        if mid in seen_markets:
            logger.debug(f"Dedup: skipping second side for market {mid[:16]}")
            continue
        seen_markets.add(mid)
        deduped_opps.append(opp)

    # Build approved orders
    approved = []
    for opp in deduped_opps:
        token_id = opp["token_id"]

        # Skip if we already hold a position in this token
        if token_id in position_ledger.positions:
            logger.debug(f"Already have position in {token_id[:16]} — skipping")
            continue

        strategy = opp.get("strategy", "resolution_timing")
        max_pct  = 0.40 if strategy == "velocity_momentum" else 0.03

        size_usdc = capital_sizer.compute_size(
            confidence=opp["confidence"],
            entry_price=opp["entry_price"],
            gross_edge_cents=opp.get("gross_edge_cents", 0.0),
            strategy=strategy,
        )
        if size_usdc < 1.0:  # minimum trade size $1
            continue

        # Cap at available capital
        available = float(position_ledger.total_capital - position_ledger.total_notional)
        size_usdc = min(size_usdc, available * 0.95)
        if size_usdc < 1.0:
            logger.info("Capital fully deployed — no room for new positions")
            break

        can_open, reason = position_ledger.can_open_position(size_usdc, max_pct=max_pct)
        if not can_open:
            logger.info(f"Risk veto: {reason}")
            continue

        approved.append({
            "market_id": opp["market_id"],
            "question": opp["question"],
            "token_id": opp["token_id"],
            "side": "BUY",
            "outcome": opp["side"],          # YES or NO — the winning side
            "price": opp["entry_price"],
            "size_usdc": size_usdc,
            "strategy": strategy,
            "confidence": opp["confidence"],
            "net_edge_cents": opp["net_edge_cents"],
            "fair_value": opp.get("fair_value", 1.0),
            # Velocity-momentum exit targets (ignored by oracle-lag positions)
            "exit_target": opp.get("exit_target", 1.0),
            "stop_price":  opp.get("stop_price", 0.0),
        })

    decision = "APPROVED" if approved else "NO_OPPORTUNITY"
    logger.info(
        f"Risk: {len(approved)} orders approved from "
        f"{len(state.get('verified_opportunities', []))} opps "
        f"({len(deduped_opps)} after dedup)"
    )

    return {
        "risk_decision": decision,
        "risk_reason": f"{len(approved)} orders approved",
        "approved_orders": approved,
        "kill_switch_active": False,
    }


async def execution_node(state: TradingState, *, lifecycle_manager, position_ledger) -> dict:
    """
    Layer 4: Submit approved orders and open positions.

    Critical bridge: after order submission the position is immediately
    registered in the position_ledger so capital is deployed and P&L tracked.
    In sim mode orders are filled at entry price on submission.
    In live mode positions open on SUBMITTED state (filled event updates later).
    """
    from core.execution.order_lifecycle import Order, OrderState
    from core.risk.position_ledger import OpenPosition
    from decimal import Decimal as D

    sim_mode = state.get("sim_mode", True)
    submitted = []

    for order_req in state.get("approved_orders", []):
        token_id = order_req["token_id"]

        # Guard: don't double-open the same position
        if token_id in position_ledger.positions:
            logger.debug(f"Position already open for {token_id[:16]} — skipping execution")
            continue

        entry_price = D(str(order_req["price"]))
        size_usdc   = D(str(order_req["size_usdc"]))

        order = Order(
            token_id=token_id,
            market_id=order_req["market_id"],
            question=order_req.get("question", ""),
            side=order_req["side"],
            outcome=order_req["outcome"],
            price=entry_price,
            size=size_usdc,
            strategy=order_req["strategy"],
            sim_mode=sim_mode,
        )
        local_id = await lifecycle_manager.submit(order)
        filled_order = lifecycle_manager.orders[local_id]

        if sim_mode:
            # In simulation: treat submission as an immediate fill at entry price
            filled_order.filled_size = size_usdc
            filled_order.avg_fill_price = entry_price
            filled_order.transition(OrderState.FILLED)

        # ── Register position in ledger ───────────────────────────────────────
        # This is the critical missing bridge: order execution → capital deployed
        if filled_order.state in {OrderState.FILLED, OrderState.LIVE, OrderState.SUBMITTED}:
            position = OpenPosition(
                token_id=token_id,
                market_id=order_req["market_id"],
                question=order_req.get("question", ""),
                side=order_req["outcome"],          # YES or NO — the winning side
                entry_price=entry_price,
                current_price=entry_price,          # mark-to-market updated each cycle
                size_usdc=size_usdc,
                strategy=order_req["strategy"],
            )
            position_ledger.open_position(position)
            logger.info(
                f"Position opened: {order_req['outcome']} "
                f"{order_req.get('question', '')[:40]} "
                f"@ {entry_price:.3f} · ${float(size_usdc):.2f} USDC "
                f"· edge {order_req.get('net_edge_cents', 0):.1f}¢"
            )

        submitted.append(filled_order.to_dict())

    orphaned = [o.local_id for o in lifecycle_manager.get_orphaned()]
    logger.info(
        f"Execution: {len(submitted)} orders filled · "
        f"{len(position_ledger.positions)} total positions · "
        f"${float(position_ledger.total_notional):.2f} deployed"
    )

    return {
        "submitted_orders": submitted,
        "orphaned_order_ids": orphaned,
    }


async def monitoring_node(state: TradingState, *, position_ledger, ws_manager=None) -> dict:
    """Layer 5: Update mark-to-market prices, compute P&L, broadcast to frontend."""
    alerts = list(state.get("system_alerts", []))

    # ── Mark-to-market: update position prices from latest orderbook / market data ──
    # For resolution timing: YES token converges to 1.00 once oracle settles.
    # Use live WS orderbook mid if available, otherwise use Gamma API mid_price.
    orderbooks = state.get("orderbooks", {})
    markets_by_token: dict[str, dict] = {}
    for m in state.get("markets", []):
        if m.get("yes_token_id"):
            markets_by_token[m["yes_token_id"]] = m
        if m.get("no_token_id"):
            markets_by_token[m["no_token_id"]] = m

    from decimal import Decimal as D
    for token_id, pos in position_ledger.positions.items():
        is_no_token = (pos.side == "NO")

        # Priority 1: live WS orderbook mid for this specific token
        if token_id in orderbooks:
            ob = orderbooks[token_id]
            mid = ob.get("mid_price")
            if mid and mid > 0:
                position_ledger.update_price(token_id, D(str(mid)))
                continue

        # Priority 2: Gamma API market mid_price
        # IMPORTANT: market.mid_price is always the YES token price.
        # For NO positions, invert it: no_price ≈ 1 - yes_mid
        if token_id in markets_by_token:
            m = markets_by_token[token_id]
            yes_mid = m.get("mid_price", 0.0)
            if yes_mid and 0.0 < yes_mid < 1.0:
                mark = (1.0 - yes_mid) if is_no_token else yes_mid
                position_ledger.update_price(token_id, D(str(round(mark, 4))))

    # ── Auto-exit velocity-momentum positions at take-profit / stop-loss / timeout ──
    from datetime import timezone
    now_dt = datetime.utcnow()
    tokens_to_exit: list[tuple[str, D, str]] = []  # (token_id, fill_price, reason)

    for token_id, pos in list(position_ledger.positions.items()):
        if pos.strategy != "velocity_momentum":
            continue

        current = float(pos.current_price)
        entry   = float(pos.entry_price)
        age_hours = (now_dt - pos.opened_at).total_seconds() / 3600

        # Derive exit targets from stored metadata (set at order-approval time)
        # Fall back to default percentages if metadata missing
        exit_target = entry * 1.25
        stop_price  = entry * 0.85
        max_hold    = 24.0

        if current >= exit_target:
            tokens_to_exit.append((token_id, D(str(current)), "TAKE_PROFIT"))
        elif current <= stop_price:
            tokens_to_exit.append((token_id, D(str(current)), "STOP_LOSS"))
        elif age_hours >= max_hold:
            tokens_to_exit.append((token_id, D(str(current)), "MAX_HOLD_TIME"))

    closed_pnls: list[float] = []
    for token_id, fill_price, reason in tokens_to_exit:
        pnl = position_ledger.close_position(token_id, fill_price)
        if pnl is not None:
            closed_pnls.append(float(pnl))
            alerts.append({
                "type":      f"VELOCITY_EXIT_{reason}",
                "message":   f"VM position exited ({reason}): {token_id[:16]} pnl={float(pnl):+.4f}",
                "severity":  "info" if float(pnl) >= 0 else "warning",
                "timestamp": time.time(),
            })
            logger.info(f"VM auto-exit [{reason}]: {token_id[:16]} pnl={float(pnl):+.4f} USDC")

    if closed_pnls:
        total_exit_pnl = sum(closed_pnls)
        logger.info(
            f"VM exits this cycle: {len(closed_pnls)} positions, "
            f"total PnL={total_exit_pnl:+.4f} USDC, "
            f"new bankroll=${float(position_ledger.total_capital):.2f}"
        )

    # Check for risk conditions
    breach = position_ledger.check_kill_conditions()
    if breach:
        alerts.append({
            "type": breach,
            "message": f"Risk breach detected: {breach}",
            "severity": "warning",
            "timestamp": time.time(),
        })

    positions_dict = position_ledger.to_dict()
    pnl_snapshot = {
        "total_capital": float(position_ledger.total_capital),
        "total_notional": float(position_ledger.total_notional),
        "unrealized_pnl": float(position_ledger.unrealized_pnl),
        "realized_pnl": float(position_ledger.realized_pnl),
        "daily_pnl": float(position_ledger.daily_pnl),
        "position_count": len(position_ledger.positions),
    }

    all_opps = state.get("verified_opportunities", [])
    vm_opps  = [o for o in all_opps if o.get("strategy") == "velocity_momentum"]
    cycle_stats = {
        "markets_scanned": len(state.get("markets", [])),
        "raw_opportunities": len(state.get("raw_opportunities", [])),
        "verified_opportunities": len(all_opps),
        "velocity_opportunities": len(vm_opps),
        "orders_submitted": len(state.get("submitted_orders", [])),
        "velocity_exits": len(tokens_to_exit),
        "cycle_id": state.get("cycle_id", ""),
        "timestamp": time.time(),
    }

    # Broadcast state to WebSocket clients
    if ws_manager:
        broadcast_payload = {
            "type": "cycle_update",
            "positions": positions_dict,
            "pnl": pnl_snapshot,
            "opportunities": state.get("verified_opportunities", []),
            "alerts": alerts,
            "markets": state.get("markets", [])[:20],  # top 20 markets
            "stats": cycle_stats,
            "kill_switch": state.get("kill_switch_active", False),
        }
        await ws_manager.broadcast(broadcast_payload)

    return {
        "positions": positions_dict,
        "pnl_snapshot": pnl_snapshot,
        "system_alerts": alerts,
        "cycle_stats": cycle_stats,
    }


async def kill_switch_node(state: TradingState, *, lifecycle_manager, kill_switch, ws_manager=None) -> dict:
    """Emergency: cancel all orders and notify frontend."""
    logger.critical("KILL SWITCH NODE EXECUTING — cancelling all orders")

    active_orders = lifecycle_manager.get_active()
    for order in active_orders:
        await lifecycle_manager.cancel(order.local_id)

    alert = {
        "type": "KILL_SWITCH_FIRED",
        "message": f"Kill switch active: {kill_switch.fire_reason}",
        "severity": "critical",
        "timestamp": time.time(),
    }

    if ws_manager:
        await ws_manager.broadcast({
            "type": "kill_switch",
            "alert": alert,
            "active": True,
        })

    return {
        "kill_switch_active": True,
        "system_alerts": [alert],
        "submitted_orders": [],
        "approved_orders": [],
    }
