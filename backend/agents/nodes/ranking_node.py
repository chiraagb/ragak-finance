"""Ranking node: fetches/recomputes fund scores for the active profile."""
from __future__ import annotations
import uuid
from agents.state import AgentState
from services.scoring_engine import get_scores
from db.models.ranking import RankingProfile
from sqlalchemy import select


async def ranking_node(state: AgentState, db) -> dict:
    profile_id_str = state.get("active_profile_id")
    if not profile_id_str:
        result = await db.execute(
            select(RankingProfile).where(RankingProfile.is_system == True, RankingProfile.name == "Emergency Fund Conservative")  # noqa: E712
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return {"ranking_data": None}
        profile_id_str = str(profile.id)

    profile_id = uuid.UUID(profile_id_str)
    scores = await get_scores(db, profile_id)

    ranking_data = {
        "profile_id": profile_id_str,
        "rankings": [
            {
                "rank": s.rank_position,
                "fund_id": str(s.fund_id),
                "total_score": float(s.total_score) if s.total_score else 0.0,
                "breakdown": s.score_breakdown or {},
                "computed_at": s.computed_at.isoformat() if s.computed_at else None,
            }
            for s in scores[:20]
        ],
    }
    return {"ranking_data": ranking_data}
