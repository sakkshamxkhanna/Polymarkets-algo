"""
LangGraph shared state — the TypedDict that flows through all graph nodes.
"""
from typing import TypedDict, Optional, Any
from decimal import Decimal


class TradingState(TypedDict):
    # Control flags
    sim_mode: bool
    kill_switch_active: bool
    cycle_id: str

    # Layer 1 outputs (Data)
    markets: list[dict]          # serialized Market objects
    orderbooks: dict[str, dict]  # token_id -> serialized OrderbookSnapshot
    ws_gap_seconds: float        # seconds since last WS message
    api_latency_ms: float        # last REST call latency

    # Layer 2 outputs (Signal)
    raw_opportunities: list[dict]       # from OracleLagMonitor
    verified_opportunities: list[dict]  # after SourceVerifier

    # Layer 3 outputs (Risk)
    risk_decision: str   # "APPROVED" | "VETOED" | "REDUCE_SIZE"
    risk_reason: str
    approved_orders: list[dict]  # OrderRequest dicts ready for submission

    # Layer 4 outputs (Execution)
    submitted_orders: list[dict]
    fills: list[dict]
    orphaned_order_ids: list[str]

    # Layer 5 outputs (Monitoring)
    positions: dict             # from PositionLedger.to_dict()
    pnl_snapshot: dict          # {total_capital, unrealized_pnl, realized_pnl, daily_pnl}
    system_alerts: list[dict]   # [{type, message, severity, timestamp}]
    cycle_stats: dict           # {markets_scanned, opportunities_found, orders_placed}

    # Strategy control flags (set via /api/strategy/{name}/toggle)
    strategy_enabled: dict      # {"resolution_timing": bool, "velocity_momentum": bool}
