"""Assembles financial_context string from all tool outputs. 6000-token budget."""
from __future__ import annotations
from agents.state import AgentState
from services.retrieval_service import compute_confidence


MAX_CONTEXT_CHARS = 24000  # ~6000 tokens


def context_assembler_node(state: AgentState) -> dict:
    parts: list[str] = []
    sources: list[dict] = []

    rag_chunks = state.get("rag_chunks", [])
    if rag_chunks:
        parts.append("=== FACTSHEET CONTEXT ===")
        for chunk in rag_chunks[:6]:
            header = f"[{chunk.get('fund_name', 'Unknown')} | {chunk.get('section_type', '')} | Page {chunk.get('page', '?')}]"
            parts.append(f"{header}\n{chunk['text']}")
            sources.append({
                "chunk_id": chunk.get("chunk_id"),
                "fund_name": chunk.get("fund_name"),
                "section_type": chunk.get("section_type"),
                "page": chunk.get("page"),
                "score": chunk.get("score"),
            })

    nav_data = state.get("nav_data")
    if nav_data:
        parts.append(f"=== NAV DATA ===\n{nav_data.get('fund_name')}: ₹{nav_data.get('nav')} (as of {nav_data.get('nav_date')})")

    comparison_data = state.get("comparison_data")
    if comparison_data:
        parts.append("=== COMPARISON DATA ===")
        fund_names = comparison_data.get("fund_names", {})
        table = comparison_data.get("comparison_table", {})
        winners = comparison_data.get("winner_per_metric", {})
        for metric_key, data in table.items():
            values_str = ", ".join(
                f"{fund_names.get(fid, fid)}: {v}{data.get('unit', '')}"
                for fid, v in data["values"].items()
                if v is not None
            )
            winner_fid = winners.get(metric_key)
            winner_str = f" → Best: {fund_names.get(winner_fid, winner_fid)}" if winner_fid else ""
            parts.append(f"{data['display_name']}: {values_str}{winner_str}")

    ranking_data = state.get("ranking_data")
    if ranking_data:
        parts.append("=== FUND RANKINGS ===")
        for entry in (ranking_data.get("rankings") or [])[:10]:
            breakdown_str = ""
            if entry.get("breakdown"):
                top_contributors = sorted(
                    entry["breakdown"].items(),
                    key=lambda x: x[1].get("weighted_contribution", 0),
                    reverse=True,
                )[:3]
                breakdown_str = " | ".join(
                    f"{k}: {v.get('weighted_contribution', 0):.2f}"
                    for k, v in top_contributors
                )
            parts.append(f"#{entry['rank']} Fund {entry['fund_id'][:8]}... — Score: {entry['total_score']:.4f} ({breakdown_str})")

    risk_data = state.get("risk_data")
    if risk_data:
        parts.append("=== RISK ANALYSIS ===")
        for fund_id, data in risk_data.items():
            signals = data.get("risk_signals", [])
            if signals:
                parts.append(f"Fund {fund_id[:8]}...:\n" + "\n".join(signals))

    context = "\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n[Context truncated to fit token budget]"

    confidence = compute_confidence(
        [type('c', (), {'score': c.get('score', 0)})() for c in rag_chunks],
        data_completeness=1.0,
    )

    return {
        "financial_context": context or None,
        "response_sources": sources,
        "confidence": confidence,
    }
