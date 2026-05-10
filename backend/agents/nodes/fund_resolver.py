"""Fund resolver node: fuzzy-matches extracted fund names to DB fund IDs."""
from __future__ import annotations
from agents.state import AgentState
from core.logging import logger


async def fund_resolver_node(state: AgentState, db) -> dict:
    fund_names = state.get("extracted_fund_names", [])
    if not fund_names:
        return {"extracted_fund_ids": []}

    from sqlalchemy import text
    fund_ids = []
    for name in fund_names:
        try:
            result = await db.execute(
                text("""
                    SELECT id, name, similarity(name, :query) AS sim
                    FROM funds
                    WHERE is_active = TRUE
                      AND similarity(name, :query) > 0.2
                    ORDER BY sim DESC
                    LIMIT 1
                """),
                {"query": name},
            )
            row = result.first()
            if row and float(row.sim) >= 0.3:
                fund_ids.append(str(row.id))
                logger.info("fund_resolved", name=name, matched=row.name, similarity=row.sim)
        except Exception as e:
            logger.warning("fund_resolve_error", name=name, error=str(e))

    return {"extracted_fund_ids": fund_ids}
