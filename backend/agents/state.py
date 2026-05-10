"""LangGraph AgentState — the contract between all graph nodes."""
from __future__ import annotations
from typing import Optional, Annotated
from typing_extensions import TypedDict
from operator import add
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    # Input
    user_query: str
    session_id: str
    user_id: Optional[str]
    active_profile_id: Optional[str]

    # Intent routing
    intent: Optional[str]
    # fund_search | comparison | rag_explain | ranking | risk_analysis | nav_lookup | general
    extracted_fund_names: list[str]
    extracted_fund_ids: list[str]

    # Tool outputs — rag_chunks uses `add` reducer so parallel nodes can both append
    nav_data: Optional[dict]
    rag_chunks: Annotated[list[dict], add]
    comparison_data: Optional[dict]
    ranking_data: Optional[dict]
    risk_data: Optional[dict]

    # Synthesis
    financial_context: Optional[str]
    response_sources: list[dict]
    confidence: Optional[str]

    # Response
    response: Optional[str]
    error: Optional[str]
    retry_count: int

    # LangGraph message history — add_messages reducer APPENDS, never overwrites
    messages: Annotated[list[BaseMessage], add_messages]
