"""
LangGraph graph construction for the Polymarket trading system.

Graph topology:
  data → (conditional) → signal → risk → (conditional) → execution → monitoring
                    ↓                              ↓
               kill_switch                    kill_switch
"""
import functools
import logging
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from .state import TradingState
from .nodes import (
    data_node,
    signal_node,
    risk_node,
    execution_node,
    monitoring_node,
    kill_switch_node,
)

logger = logging.getLogger(__name__)


def route_after_data(state: TradingState) -> str:
    if state.get("kill_switch_active"):
        return "kill_switch"
    return "signal"


def route_after_risk(state: TradingState) -> str:
    if state.get("kill_switch_active"):
        return "kill_switch"
    if state.get("risk_decision") == "VETOED":
        return "monitoring"
    if not state.get("approved_orders"):
        return "monitoring"
    return "execution"


def build_graph(
    rest_poller,
    ws_feed,
    oracle_monitor,
    source_verifier,
    fair_value_engine,
    kill_switch,
    position_ledger,
    capital_sizer,
    lifecycle_manager,
    ws_manager=None,
    velocity_scanner=None,
) -> tuple[Any, Any]:
    """
    Build and compile the LangGraph trading graph.
    Returns (compiled_app, checkpointer).
    """

    # Bind dependencies to node functions via partial application
    bound_data = functools.partial(data_node, rest_poller=rest_poller, ws_feed=ws_feed)
    bound_signal = functools.partial(
        signal_node,
        oracle_monitor=oracle_monitor,
        source_verifier=source_verifier,
        fair_value_engine=fair_value_engine,
        velocity_scanner=velocity_scanner,
    )
    bound_risk = functools.partial(
        risk_node,
        kill_switch=kill_switch,
        position_ledger=position_ledger,
        capital_sizer=capital_sizer,
    )
    bound_execution = functools.partial(
        execution_node,
        lifecycle_manager=lifecycle_manager,
        position_ledger=position_ledger,
    )
    bound_monitoring = functools.partial(
        monitoring_node,
        position_ledger=position_ledger,
        ws_manager=ws_manager,
    )
    bound_kill_switch = functools.partial(
        kill_switch_node,
        lifecycle_manager=lifecycle_manager,
        kill_switch=kill_switch,
        ws_manager=ws_manager,
    )

    graph = StateGraph(TradingState)

    graph.add_node("data", bound_data)
    graph.add_node("signal", bound_signal)
    graph.add_node("risk", bound_risk)
    graph.add_node("execution", bound_execution)
    graph.add_node("monitoring", bound_monitoring)
    graph.add_node("kill_switch", bound_kill_switch)

    graph.set_entry_point("data")

    graph.add_conditional_edges(
        "data",
        route_after_data,
        {"signal": "signal", "kill_switch": "kill_switch"},
    )
    graph.add_edge("signal", "risk")
    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "execution": "execution",
            "monitoring": "monitoring",
            "kill_switch": "kill_switch",
        },
    )
    graph.add_edge("execution", "monitoring")
    graph.add_edge("monitoring", END)
    graph.add_edge("kill_switch", END)

    # In-memory checkpointer — each cycle is independent, trade audit trail
    # is persisted via SQLAlchemy (TradeJournal/SystemEvent tables)
    checkpointer = InMemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("LangGraph trading graph compiled successfully")
    return compiled, checkpointer
