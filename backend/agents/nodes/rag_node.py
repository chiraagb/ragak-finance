"""RAG node: hybrid semantic + keyword retrieval from factsheet chunks."""
from __future__ import annotations
import uuid
from agents.state import AgentState
from services.retrieval_service import hybrid_search


async def rag_node(state: AgentState, db) -> dict:
    query = state["user_query"]
    fund_id_strs = state.get("extracted_fund_ids", [])
    intent = state.get("intent", "general")

    fund_ids = [uuid.UUID(fid) for fid in fund_id_strs if fid]
    section_filter = _section_for_intent(intent)

    chunks = await hybrid_search(
        session=db,
        query=query,
        fund_ids=fund_ids if fund_ids else None,
        section_filter=section_filter,
        top_k=8,
    )

    return {
        "rag_chunks": [
            {
                "chunk_id": c.chunk_id,
                "text": c.chunk_text,
                "fund_name": c.fund_name,
                "page": c.page_number,
                "section_type": c.section_type,
                "score": c.score,
            }
            for c in chunks
        ]
    }


def _section_for_intent(intent: str) -> str | None:
    return {
        "risk_analysis": "credit_quality",
        "rag_explain": None,
    }.get(intent)
