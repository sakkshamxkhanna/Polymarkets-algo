"""
FastAPI application — REST + WebSocket bridge between trading backend and React frontend.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ws_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Global references — injected by main.py at startup
_state: dict[str, Any] = {
    "kill_switch": None,
    "position_ledger": None,
    "lifecycle_manager": None,
    "rest_poller": None,
    "ws_feed": None,
    "pnl_engine": None,
    "sim_mode": True,
    "last_cycle": None,
    # Oracle lag is disabled: UMA oracle has 100+ day delay, capital gets locked.
    # Velocity momentum trades active markets with real-time data and exits in <24h.
    "strategy_enabled": {"resolution_timing": False, "velocity_momentum": True},
}

ws_manager = WebSocketManager()


def create_app(state: dict) -> FastAPI:
    _state.update(state)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("FastAPI started")
        yield
        logger.info("FastAPI shutting down")

    app = FastAPI(
        title="Polymarket Trading System",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── WebSocket ─────────────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_manager.connect(ws)
        try:
            while True:
                # Keep connection alive; data flows from backend → frontend via broadcast
                await ws.receive_text()
        except WebSocketDisconnect:
            await ws_manager.disconnect(ws)

    # ─── Markets ────────────────────────────────────────────────────────────────

    @app.get("/api/markets")
    async def get_markets(limit: int = 50, active_only: bool = True):
        poller = _state.get("rest_poller")
        if not poller:
            return {"markets": [], "total": 0}
        markets = poller.markets[:limit]
        return {
            "markets": [
                {
                    "condition_id": m.condition_id,
                    "question": m.question,
                    "end_date": m.end_date.isoformat(),
                    "volume_usd": m.volume_usd,
                    "yes_token_id": m.yes_token_id,
                    "no_token_id": m.no_token_id,
                    "category": m.category,
                    "is_active": m.is_active,
                    "hours_to_resolution": m.hours_to_resolution,
                    "mid_price": m.mid_price,
                    "spread_cents": m.spread_cents,
                }
                for m in markets
            ],
            "total": len(markets),
        }

    @app.get("/api/orderbook/{token_id}")
    async def get_orderbook(token_id: str):
        feed = _state.get("ws_feed")
        if not feed or token_id not in feed.books:
            raise HTTPException(status_code=404, detail="Orderbook not found")
        book = feed.books[token_id]
        return {
            "token_id": token_id,
            "best_bid": float(book.best_bid) if book.best_bid else None,
            "best_ask": float(book.best_ask) if book.best_ask else None,
            "mid_price": float(book.mid_price) if book.mid_price else None,
            "spread_cents": book.spread_cents,
            "bids": [{"price": float(b.price), "size": float(b.size)} for b in book.bids[:20]],
            "asks": [{"price": float(a.price), "size": float(a.size)} for a in book.asks[:20]],
            "timestamp": book.timestamp,
        }

    # ─── Positions & P&L ────────────────────────────────────────────────────────

    @app.get("/api/positions")
    async def get_positions():
        ledger = _state.get("position_ledger")
        if not ledger:
            return {"positions": [], "summary": {}}
        data = ledger.to_dict()
        return data

    @app.get("/api/pnl")
    async def get_pnl():
        ledger = _state.get("position_ledger")
        engine = _state.get("pnl_engine")
        if not ledger:
            return {}
        summary = {
            "total_capital": float(ledger.total_capital),
            "total_notional": float(ledger.total_notional),
            "unrealized_pnl": float(ledger.unrealized_pnl),
            "realized_pnl": float(ledger.realized_pnl),
            "daily_pnl": float(ledger.daily_pnl),
        }
        if engine:
            summary.update(engine.summary())
        return summary

    # ─── Trades ─────────────────────────────────────────────────────────────────

    @app.get("/api/trades")
    async def get_trades(limit: int = 50):
        mgr = _state.get("lifecycle_manager")
        if not mgr:
            return {"trades": []}
        orders = sorted(mgr.orders.values(), key=lambda o: o.created_at, reverse=True)
        return {"trades": [o.to_dict() for o in orders[:limit]]}

    # ─── System Status ───────────────────────────────────────────────────────────

    @app.get("/api/system/status")
    async def get_system_status():
        ks = _state.get("kill_switch")
        feed = _state.get("ws_feed")
        mgr = _state.get("lifecycle_manager")
        return {
            "sim_mode": _state.get("sim_mode", True),
            "kill_switch": ks.to_dict() if ks else {},
            "ws_connected": feed is not None and feed.is_connected and feed.ws_gap_seconds < 30,
            "ws_gap_seconds": feed.ws_gap_seconds if feed else 0,
            "ws_clients": ws_manager.connection_count,
            "active_orders": len(mgr.get_active()) if mgr else 0,
            "orphaned_orders": len(mgr.get_orphaned()) if mgr else 0,
            "strategy_enabled": _state.get("strategy_enabled", {}),
            "last_cycle": _state.get("last_cycle"),
            "uptime": time.time(),
        }

    @app.get("/api/debug/scan")
    async def debug_scan():
        """
        Run a one-shot strategy scan and return raw results — useful for testing
        without waiting for the 60s trading loop cycle.
        """
        poller = _state.get("rest_poller")
        feed = _state.get("ws_feed")
        if not poller:
            return {"error": "poller not ready"}

        from core.signal.oracle_lag_monitor import OracleLagMonitor
        from core.signal.source_verifier import SourceVerifier
        from core.data.normalization import Market, OrderbookSnapshot, PriceLevel
        from datetime import datetime
        from decimal import Decimal

        markets = poller.markets
        now = str(datetime.utcnow().isoformat())

        # Count markets by resolution window
        from datetime import timedelta
        dt_now = datetime.utcnow()
        within_6h = [m for m in markets if m.end_date <= dt_now + timedelta(hours=6)]
        past_end  = [m for m in markets if m.end_date <= dt_now]
        oracle_pending = [m for m in past_end if not m.oracle_submitted]

        monitor = OracleLagMonitor(min_edge_cents=6.0)
        verifier = SourceVerifier()

        raw_opps = monitor.scan(markets, feed.books if feed else {}, 500.0, 0.0)

        verified = []
        for opp in raw_opps:
            result = verifier.verify(opp.market, opp.side)
            verified.append({
                "question": opp.market.question[:60],
                "side": opp.side,
                "entry_price": float(opp.entry_price),
                "gross_edge_cents": opp.gross_edge_cents,
                "hours_to_resolution": opp.hours_to_resolution,
                "confirmed": result.confirmed,
                "confidence": result.confidence,
                "reason": result.reason,
            })

        return {
            "timestamp": now,
            "total_markets": len(markets),
            "within_6h_of_resolution": len(within_6h),
            "past_end_date": len(past_end),
            "oracle_pending": len(oracle_pending),
            "orderbooks_live": len(feed.books) if feed else 0,
            "raw_opportunities": len(raw_opps),
            "verified_opportunities": verified,
        }

    @app.post("/api/system/kill-switch")
    async def trigger_kill_switch(action: dict):
        ks = _state.get("kill_switch")
        if not ks:
            raise HTTPException(status_code=503, detail="Kill switch not initialized")
        cmd = action.get("action", "fire")
        if cmd == "fire":
            await ks.fire("Manual trigger by operator")
            return {"status": "fired", "reason": "Manual trigger"}
        elif cmd == "reset":
            ks.reset()
            return {"status": "reset"}
        raise HTTPException(status_code=400, detail=f"Unknown action: {cmd}")

    @app.post("/api/strategy/run-now")
    async def run_strategy_now():
        """
        Immediately trigger one full trading cycle — skips the 60s wait.
        Returns the last_cycle stats captured after the cycle completes,
        or a 'triggered' ack if the cycle hasn't finished within 1s.
        """
        ks = _state.get("kill_switch")
        if ks and ks.is_active:
            raise HTTPException(
                status_code=409,
                detail=f"Kill switch is active: {ks.fire_reason}",
            )
        trigger: asyncio.Event = _state.get("manual_trigger")
        if not trigger:
            raise HTTPException(status_code=503, detail="Trading loop not ready")
        trigger.set()
        logger.info("Manual run-now triggered via API")
        return {
            "status": "triggered",
            "message": "Trading cycle started — results appear in /api/system/status",
        }

    @app.post("/api/strategy/{name}/toggle")
    async def toggle_strategy(name: str, body: dict):
        enabled = body.get("enabled", True)
        _state["strategy_enabled"][name] = enabled
        logger.info(f"Strategy '{name}' {'enabled' if enabled else 'disabled'}")
        return {"strategy": name, "enabled": enabled}

    @app.post("/api/system/sim-mode")
    async def set_sim_mode(body: dict):
        enabled = body.get("enabled", True)
        _state["sim_mode"] = enabled
        mgr = _state.get("lifecycle_manager")
        if mgr:
            mgr.sim_mode = enabled
        return {"sim_mode": enabled}

    @app.post("/api/subscribe")
    async def subscribe_tokens(body: dict):
        """Subscribe WS feed to specific token IDs on demand."""
        feed = _state.get("ws_feed")
        if not feed:
            return {"subscribed": 0}
        token_ids = body.get("token_ids", [])[:20]
        if token_ids:
            await feed.subscribe(token_ids)
        return {"subscribed": len(token_ids)}

    @app.get("/api/history/{token_id}")
    async def get_price_history(token_id: str, interval: str = "1d"):
        """Proxy Polymarket CLOB history endpoint for price charts."""
        import httpx
        resolution_map = {"1h": "1", "1d": "60", "1w": "1440", "max": "1440"}
        resolution = resolution_map.get(interval, "60")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://clob.polymarket.com/prices-history",
                    params={"market": token_id, "interval": interval, "fidelity": resolution},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"History fetch failed for {token_id}: {e}")
        return {"history": []}

    @app.post("/api/orders/manual")
    async def submit_manual_order(body: dict):
        """Submit a manual simulated order from the UI."""
        from core.execution.order_lifecycle import Order
        from decimal import Decimal
        mgr = _state.get("lifecycle_manager")
        if not mgr:
            raise HTTPException(status_code=503, detail="Order manager not ready")
        try:
            order = Order(
                token_id=body["token_id"],
                market_id=body.get("market_id", ""),
                question=body.get("question", ""),
                side="BUY",
                outcome=body.get("outcome", "YES"),
                price=Decimal(str(body["price"])),
                size=Decimal(str(body["size_usdc"])),
                strategy="manual",
                sim_mode=True,
            )
            local_id = await mgr.submit(order)
            return {"status": "submitted", "local_id": local_id, "order": mgr.orders[local_id].to_dict()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/calibration")
    async def get_calibration():
        last_cycle = _state.get("last_cycle", {})
        return {
            "opportunities_found": last_cycle.get("verified_opportunities", 0) if last_cycle else 0,
            "cycle_stats": last_cycle,
        }

    @app.post("/api/positions/close-all")
    async def close_all_positions():
        """
        Close all open positions at current mark price and clear the ledger.
        Used to exit bad positions before strategy refinements take effect.
        """
        ledger = _state.get("position_ledger")
        if not ledger:
            raise HTTPException(status_code=503, detail="Position ledger not ready")
        from decimal import Decimal
        closed = []
        for token_id, pos in list(ledger.positions.items()):
            pnl = ledger.close_position(token_id, pos.current_price)
            closed.append({
                "token_id": token_id,
                "question": pos.question,
                "side": pos.side,
                "entry_price": float(pos.entry_price),
                "exit_price": float(pos.current_price),
                "realized_pnl": float(pnl) if pnl else 0.0,
            })
        logger.info(f"Closed {len(closed)} positions via API")
        return {"closed": len(closed), "positions": closed, "realized_pnl": sum(p["realized_pnl"] for p in closed)}

    return app
