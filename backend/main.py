"""
Polymarket Trading System — Main Orchestrator

Starts all layers as asyncio tasks, builds LangGraph, runs trading loop.
SIM_MODE=True (default) routes all orders to MatchingSimulator.
"""
import asyncio
import logging
import sys
import uuid
from pathlib import Path

import uvicorn

# Ensure backend/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from db.models import init_db
from core.data.ws_feed import WebSocketBookFeed
from core.data.rest_poller import RESTPoller
from core.signal.oracle_lag_monitor import OracleLagMonitor
from core.signal.velocity_momentum import VelocityMomentumScanner
from core.signal.source_verifier import SourceVerifier
from core.signal.fair_value_engine import FairValueEngine
from core.risk.position_ledger import PositionLedger
from core.risk.kill_switch import KillSwitch
from core.risk.capital_sizer import CapitalSizer
from core.execution.order_lifecycle import OrderLifecycleManager
from core.execution.dead_man_switch import DeadManSwitch
from core.execution.rate_limit_budget import RateLimitBudget
from core.monitoring.pnl_engine import PnLEngine
from core.graph.builder import build_graph
from api.server import create_app, ws_manager, _state as api_state
from api.ws_manager import WebSocketManager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")


async def main():
    logger.info("=" * 60)
    logger.info("Polymarket Trading System starting...")
    logger.info(f"Mode: {'SIMULATION' if settings.sim_mode else '⚠️  LIVE TRADING'}")
    logger.info(f"Capital: ${settings.max_capital_usd:.0f} USDC")
    logger.info("=" * 60)

    # Initialize DB
    await init_db()

    # ── Instantiate all components ──────────────────────────────────────────────
    ws_feed = WebSocketBookFeed(ws_host=settings.ws_host)
    rest_poller = RESTPoller(gamma_host=settings.gamma_host, clob_host=settings.clob_host)
    oracle_monitor    = OracleLagMonitor(min_edge_cents=settings.min_edge_cents)
    velocity_scanner  = VelocityMomentumScanner(min_edge=0.15, max_hours=72.0)
    source_verifier   = SourceVerifier()
    fair_value_engine = FairValueEngine()
    position_ledger = PositionLedger(total_capital=settings.max_capital_usd)
    capital_sizer = CapitalSizer(total_capital=settings.max_capital_usd)
    rate_limiter = RateLimitBudget()
    pnl_engine = PnLEngine()

    # Kill switch with cancel-all callback
    lifecycle_manager = OrderLifecycleManager(sim_mode=settings.sim_mode)

    async def cancel_all_orders():
        for order in lifecycle_manager.get_active():
            await lifecycle_manager.cancel(order.local_id)
        logger.warning("All orders cancelled by kill switch")

    kill_switch = KillSwitch(on_fire=cancel_all_orders)
    dead_man = DeadManSwitch(cancel_all_fn=cancel_all_orders)

    # ── Build LangGraph ─────────────────────────────────────────────────────────
    graph_app, checkpointer = build_graph(
        rest_poller=rest_poller,
        ws_feed=ws_feed,
        oracle_monitor=oracle_monitor,
        source_verifier=source_verifier,
        fair_value_engine=fair_value_engine,
        kill_switch=kill_switch,
        position_ledger=position_ledger,
        capital_sizer=capital_sizer,
        lifecycle_manager=lifecycle_manager,
        ws_manager=ws_manager,
        velocity_scanner=velocity_scanner,
    )

    # ── Manual trigger event (set by /api/strategy/run-now) ────────────────────
    manual_trigger = asyncio.Event()

    # ── FastAPI app ─────────────────────────────────────────────────────────────
    fastapi_app = create_app({
        "kill_switch": kill_switch,
        "position_ledger": position_ledger,
        "lifecycle_manager": lifecycle_manager,
        "rest_poller": rest_poller,
        "ws_feed": ws_feed,
        "pnl_engine": pnl_engine,
        "sim_mode": settings.sim_mode,
        "manual_trigger": manual_trigger,
    })

    # ── Trading loop ─────────────────────────────────────────────────────────────
    async def trading_loop():
        logger.info("Trading loop started. Waiting for initial market data...")
        await asyncio.sleep(10)  # let REST poller fetch first batch

        config = {"configurable": {"thread_id": "main-trading-thread"}}
        cycle_num = 0

        while True:
            if kill_switch.is_active:
                reason = kill_switch.fire_reason or ""
                # Auto-recover from WS_FEED_DEAD once feed reconnects
                # (oracle-pending markets don't trade; quiet feed ≠ dead system)
                if "WS_FEED_DEAD" in reason and ws_feed.is_connected:
                    logger.warning("WS reconnected — auto-resetting kill switch from WS_FEED_DEAD")
                    kill_switch.reset()
                else:
                    logger.warning(f"Kill switch active ({reason}) — trading loop paused")
                    await asyncio.sleep(30)
                    continue

            cycle_num += 1
            cycle_id = str(uuid.uuid4())[:8]
            logger.info(f"━━━ Cycle #{cycle_num} [{cycle_id}] ━━━")

            dead_man.heartbeat()

            initial_state: dict = {
                "sim_mode": settings.sim_mode,
                "kill_switch_active": kill_switch.is_active,
                "cycle_id": cycle_id,
                "markets": [],
                "orderbooks": {},
                "ws_gap_seconds": ws_feed.ws_gap_seconds,
                "api_latency_ms": 0.0,
                "raw_opportunities": [],
                "verified_opportunities": [],
                "risk_decision": "PENDING",
                "risk_reason": "",
                "approved_orders": [],
                "submitted_orders": [],
                "fills": [],
                "orphaned_order_ids": [],
                "positions": {},
                "pnl_snapshot": position_ledger.to_dict(),
                "system_alerts": [],
                "cycle_stats": {},
                # Pass live strategy toggle flags from API state into the graph
                "strategy_enabled": api_state.get("strategy_enabled", {"resolution_timing": False}),
            }

            try:
                async with checkpointer as cp:
                    compiled = graph_app
                    async for event in compiled.astream_events(
                        initial_state, config, version="v2"
                    ):
                        await ws_manager.broadcast_event(event)
                        # Keep last_cycle in sync for /api/system/status
                        if (event.get("event") == "on_chain_end"
                                and event.get("name") == "monitoring"):
                            output = event.get("data", {}).get("output", {})
                            if cycle_stats := output.get("cycle_stats"):
                                api_state["last_cycle"] = cycle_stats
            except Exception as e:
                logger.error(f"Graph cycle error: {e}", exc_info=True)
                await ws_manager.broadcast({
                    "type": "system_alert",
                    "message": f"Cycle error: {str(e)[:200]}",
                    "severity": "warning",
                })

            # Wait up to 60s, but wake immediately if /api/strategy/run-now fires
            try:
                await asyncio.wait_for(manual_trigger.wait(), timeout=60)
                manual_trigger.clear()
                logger.info("Manual trigger received — starting immediate cycle")
            except asyncio.TimeoutError:
                pass  # normal 60s cadence

    # ── Orderbook subscription task ──────────────────────────────────────────────
    async def subscribe_top_markets():
        """Subscribe to orderbook WS feed — oracle-pending markets first, then top 50 by volume."""
        from datetime import datetime, timedelta
        subscribed: set[str] = set()
        while True:
            all_markets = rest_poller.markets
            now = datetime.utcnow()

            # Priority 1: markets that have passed end_date and oracle not yet submitted
            oracle_pending = [m for m in all_markets
                              if m.end_date <= now and not m.oracle_submitted]
            # Priority 2: markets resolving within 48h
            near_resolution = [m for m in all_markets
                                if now < m.end_date <= now + timedelta(hours=48)]
            # Priority 3: top markets by volume
            top_vol = sorted(all_markets, key=lambda m: m.volume_usd, reverse=True)[:40]

            priority_markets = oracle_pending + near_resolution + top_vol
            new_tokens = []
            for m in priority_markets:
                for tid in [m.yes_token_id, m.no_token_id]:
                    if tid and tid not in subscribed:
                        new_tokens.append(tid)
                        subscribed.add(tid)

            if new_tokens:
                await ws_feed.subscribe(new_tokens)
                logger.info(
                    f"Subscribed {len(new_tokens)} tokens "
                    f"({len(oracle_pending)} oracle-pending, {len(near_resolution)} near-res, "
                    f"{len(top_vol)} top-vol)"
                )
            await asyncio.sleep(60)

    # ── Start everything ─────────────────────────────────────────────────────────
    config = uvicorn.Config(
        app=fastapi_app,
        host=settings.backend_host,
        port=settings.backend_port,
        log_level="warning",  # suppress uvicorn noise
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        rest_poller.run(),
        ws_feed.run(),
        dead_man.run(),
        trading_loop(),
        subscribe_top_markets(),
        server.serve(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
