"""LangGraph state graph builder for RAGAK.

Graph topology:
  START → intent_detector → fund_resolver → [rag_node|comparison_node|ranking_node|risk_node]
        → context_assembler → response_synthesizer → END
"""
from __future__ import annotations
import functools
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from agents.state import AgentState
from agents.nodes.intent_detector import intent_detector_node
from agents.nodes.fund_resolver import fund_resolver_node
from agents.nodes.rag_node import rag_node
from agents.nodes.comparison_node import comparison_node
from agents.nodes.ranking_node import ranking_node
from agents.nodes.risk_node import risk_node
from agents.nodes.context_assembler import context_assembler_node
from agents.nodes.response_synthesizer import response_synthesizer_node


def _route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "ranking":
        return "ranking_node"
    if intent == "general":
        return "rag_node"
    return "fund_resolver"


def _route_after_resolver(state: AgentState) -> list[Send] | str:
    intent = state.get("intent", "general")
    fund_ids = state.get("extracted_fund_ids", [])

    if intent == "comparison" and len(fund_ids) >= 2:
        return [
            Send("comparison_node", state),
            Send("rag_node", state),
        ]
    if intent == "risk_analysis":
        return [
            Send("risk_node", state),
            Send("rag_node", state),
        ]
    if intent in ("rag_explain", "fund_search"):
        return "rag_node"
    if intent == "nav_lookup":
        return "rag_node"
    return "rag_node"


def _wrap_with_db(node_fn, db):
    """Wrap an async node function that requires a db session."""
    async def wrapped(state: AgentState) -> dict:
        return await node_fn(state, db)
    wrapped.__name__ = node_fn.__name__
    return wrapped


def build_graph(db=None, checkpointer=None) -> StateGraph:
    """
    Build and compile the LangGraph state graph.
    `db` is an AsyncSession injected at runtime per-request.
    `checkpointer` is a LangGraph PostgresSaver for session persistence.
    """
    builder = StateGraph(AgentState)

    builder.add_node("intent_detector", intent_detector_node)
    builder.add_node("fund_resolver", _wrap_with_db(fund_resolver_node, db))
    builder.add_node("rag_node", _wrap_with_db(rag_node, db))
    builder.add_node("comparison_node", _wrap_with_db(comparison_node, db))
    builder.add_node("ranking_node", _wrap_with_db(ranking_node, db))
    builder.add_node("risk_node", _wrap_with_db(risk_node, db))
    builder.add_node("context_assembler", context_assembler_node)
    builder.add_node("response_synthesizer", response_synthesizer_node)

    builder.add_edge(START, "intent_detector")
    builder.add_conditional_edges("intent_detector", _route_after_intent, {
        "fund_resolver": "fund_resolver",
        "ranking_node": "ranking_node",
        "rag_node": "rag_node",
    })
    builder.add_conditional_edges("fund_resolver", _route_after_resolver, {
        "comparison_node": "comparison_node",
        "rag_node": "rag_node",
        "risk_node": "risk_node",
    })

    for node in ["rag_node", "comparison_node", "ranking_node", "risk_node"]:
        builder.add_edge(node, "context_assembler")

    builder.add_edge("context_assembler", "response_synthesizer")
    builder.add_edge("response_synthesizer", END)

    return builder.compile(checkpointer=checkpointer)
