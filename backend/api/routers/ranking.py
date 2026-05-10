"""Ranking profiles, scores, and comparison endpoints."""
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, validator

from db.session import get_db
from db.models.ranking import RankingProfile, RankingProfileWeight, FundRankingScore
from db.models.fund import Fund
from db.models.fund_metric import MetricDefinition
from api.dependencies import get_current_user, require_admin
from db.models.user import User
from services.scoring_engine import compute_scores_for_profile, get_scores

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


class CreateProfileRequest(BaseModel):
    name: str
    description: Optional[str] = None
    weights: dict[str, float]
    is_public: bool = False

    @validator("weights")
    def weights_must_sum_to_one(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        return v


class ProfileResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_system: bool
    is_public: bool
    weights: list[dict]


@router.get("/profiles")
async def list_profiles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RankingProfile).where(
            (RankingProfile.is_system == True) | (RankingProfile.owner_id == user.id)  # noqa: E712
        )
    )
    profiles = result.scalars().all()
    return [{"id": str(p.id), "name": p.name, "is_system": p.is_system, "is_public": p.is_public} for p in profiles]


@router.post("/profiles", status_code=201)
async def create_profile(
    body: CreateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    metric_map = await _build_metric_map(db)

    for key in body.weights:
        if key not in metric_map:
            raise HTTPException(status_code=400, detail=f"Unknown metric key: {key}")

    profile = RankingProfile(
        name=body.name,
        description=body.description,
        owner_id=user.id,
        is_public=body.is_public,
    )
    db.add(profile)
    await db.flush()

    for key, weight in body.weights.items():
        db.add(RankingProfileWeight(profile_id=profile.id, metric_id=metric_map[key], weight=weight))

    return {"id": str(profile.id), "name": profile.name}


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await _get_profile_or_404(db, profile_id, user)
    weights_result = await db.execute(
        select(RankingProfileWeight, MetricDefinition)
        .join(MetricDefinition, RankingProfileWeight.metric_id == MetricDefinition.id)
        .where(RankingProfileWeight.profile_id == profile_id)
    )
    weights = [
        {
            "metric_key": row.MetricDefinition.key,
            "display_name": row.MetricDefinition.display_name,
            "weight": float(row.RankingProfileWeight.weight),
            "higher_is_better": row.MetricDefinition.higher_is_better,
            "unit": row.MetricDefinition.unit,
        }
        for row in weights_result.all()
    ]
    return {"id": str(profile.id), "name": profile.name, "description": profile.description, "is_system": profile.is_system, "weights": weights}


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: uuid.UUID,
    body: CreateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(db, profile_id, user)
    if profile.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify system profiles. Clone it first.")

    metric_map = await _build_metric_map(db)
    existing_weights = await db.execute(select(RankingProfileWeight).where(RankingProfileWeight.profile_id == profile_id))
    for w in existing_weights.scalars().all():
        await db.delete(w)

    for key, weight in body.weights.items():
        db.add(RankingProfileWeight(profile_id=profile_id, metric_id=metric_map[key], weight=weight))

    existing_scores = await db.execute(select(FundRankingScore).where(FundRankingScore.profile_id == profile_id))
    for s in existing_scores.scalars().all():
        await db.delete(s)

    return {"id": str(profile_id), "message": "Profile updated, scores invalidated"}


@router.post("/profiles/{profile_id}/clone", status_code=201)
async def clone_profile(profile_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    original = await _get_profile_or_404(db, profile_id, user, allow_system=True)
    new_profile = RankingProfile(
        name=f"{original.name} (Copy)",
        description=original.description,
        owner_id=user.id,
        is_system=False,
        is_public=False,
    )
    db.add(new_profile)
    await db.flush()

    weights_result = await db.execute(select(RankingProfileWeight).where(RankingProfileWeight.profile_id == profile_id))
    for w in weights_result.scalars().all():
        db.add(RankingProfileWeight(profile_id=new_profile.id, metric_id=w.metric_id, weight=w.weight))

    return {"id": str(new_profile.id), "name": new_profile.name}


@router.get("/scores")
async def get_fund_scores(
    profile_id: uuid.UUID,
    top_n: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(db, profile_id, user, allow_system=True)
    scores = await get_scores(db, profile_id)

    fund_ids = [s.fund_id for s in scores[:top_n]]
    funds_result = await db.execute(select(Fund).where(Fund.id.in_(fund_ids)))
    fund_map = {f.id: f for f in funds_result.scalars().all()}

    return [
        {
            "rank": s.rank_position,
            "fund_id": str(s.fund_id),
            "fund_name": fund_map.get(s.fund_id, type("F", (), {"name": "Unknown"})()).name,
            "total_score": float(s.total_score) if s.total_score else 0.0,
            "score_breakdown": s.score_breakdown or {},
            "computed_at": s.computed_at.isoformat() if s.computed_at else None,
        }
        for s in scores[:top_n]
    ]


@router.get("/compare")
async def compare_funds(
    fund_ids: str,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ids = [uuid.UUID(x.strip()) for x in fund_ids.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 fund IDs")
    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 funds for comparison")

    await compute_scores_for_profile(db, profile_id, fund_ids=ids)
    scores_result = await db.execute(
        select(FundRankingScore, Fund)
        .join(Fund, FundRankingScore.fund_id == Fund.id)
        .where(FundRankingScore.fund_id.in_(ids), FundRankingScore.profile_id == profile_id)
    )
    return [
        {
            "fund_id": str(row.FundRankingScore.fund_id),
            "fund_name": row.Fund.name,
            "rank_in_comparison": None,
            "total_score": float(row.FundRankingScore.total_score) if row.FundRankingScore.total_score else 0.0,
            "breakdown": row.FundRankingScore.score_breakdown or {},
        }
        for row in sorted(scores_result.all(), key=lambda r: r.FundRankingScore.total_score or 0, reverse=True)
    ]


class PreviewWeightsRequest(BaseModel):
    weights: dict[str, float]

    @validator("weights")
    def weights_must_sum_to_one(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        return v


@router.post("/profiles/preview")
async def preview_rankings(
    body: PreviewWeightsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute rankings for given weights without persisting a profile."""
    from services.scoring_engine import compute_scores_for_profile, _normalize
    from db.models.fund_metric import FundMetric

    metric_map = await _build_metric_map(db)
    for key in body.weights:
        if key not in metric_map:
            raise HTTPException(status_code=400, detail=f"Unknown metric key: {key}")

    # Create a temporary in-memory profile object for scoring
    import uuid as _uuid
    temp_id = _uuid.uuid4()

    # Reuse scoring engine by building a transient profile row
    profile = RankingProfile(id=temp_id, name="_preview", scoring_model="weighted_sum")
    db.add(profile)
    await db.flush()

    for key, weight in body.weights.items():
        db.add(RankingProfileWeight(
            profile_id=temp_id,
            metric_id=metric_map[key],
            weight=weight,
        ))
    await db.flush()

    results = await compute_scores_for_profile(db, temp_id)

    # Roll back the transient profile so it's not persisted
    await db.rollback()

    fund_ids = [r.fund_id for r in results[:10]]
    funds_result = await db.execute(select(Fund).where(Fund.id.in_(fund_ids)))
    fund_map = {f.id: f.name for f in funds_result.scalars().all()}

    return [
        {
            "rank": i + 1,
            "fund_id": str(r.fund_id),
            "fund_name": fund_map.get(r.fund_id, "Unknown"),
            "total_score": r.total_score,
        }
        for i, r in enumerate(results[:10])
    ]


async def _build_metric_map(db: AsyncSession) -> dict[str, uuid.UUID]:
    result = await db.execute(select(MetricDefinition))
    return {m.key: m.id for m in result.scalars().all()}


async def _get_profile_or_404(
    db: AsyncSession,
    profile_id: uuid.UUID,
    user: User,
    allow_system: bool = False,
) -> RankingProfile:
    result = await db.execute(select(RankingProfile).where(RankingProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not allow_system and profile.is_system:
        pass
    if not profile.is_system and profile.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return profile
