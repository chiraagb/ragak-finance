"""Deterministic financial scoring engine. No AI. No randomness. Fully testable."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.models.fund import Fund
from db.models.fund_metric import MetricDefinition, FundMetric
from db.models.ranking import RankingProfile, RankingProfileWeight, FundRankingScore


@dataclass
class MetricScoreDetail:
    raw_value: Optional[float]
    normalized_score: float
    weight: float
    weighted_contribution: float
    unit: str
    higher_is_better: bool


@dataclass
class ScoringResult:
    fund_id: uuid.UUID
    total_score: float
    breakdown: dict[str, MetricScoreDetail]
    missing_metrics: list[str]
    data_completeness: float


def _normalize(value: float, higher_is_better: bool, all_values: list[float]) -> float:
    valid = [v for v in all_values if v is not None]
    if not valid:
        return 0.5
    min_v, max_v = min(valid), max(valid)
    if max_v == min_v:
        return 0.5
    n = (value - min_v) / (max_v - min_v)
    return (1.0 - n) if not higher_is_better else n


async def compute_scores_for_profile(
    session: AsyncSession,
    profile_id: uuid.UUID,
    fund_ids: Optional[list[uuid.UUID]] = None,
) -> list[ScoringResult]:
    """
    Compute weighted-sum scores for all (or specified) active funds against a ranking profile.
    Persists results to fund_ranking_scores table.
    Returns list of ScoringResult sorted by total_score descending.
    """
    profile_result = await session.execute(
        select(RankingProfile).where(RankingProfile.id == profile_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise ValueError(f"Profile {profile_id} not found")

    weights_result = await session.execute(
        select(RankingProfileWeight, MetricDefinition)
        .join(MetricDefinition, RankingProfileWeight.metric_id == MetricDefinition.id)
        .where(RankingProfileWeight.profile_id == profile_id)
    )
    weight_rows = weights_result.all()
    if not weight_rows:
        raise ValueError(f"Profile {profile_id} has no weights configured")

    funds_query = select(Fund).where(Fund.is_active == True)  # noqa: E712
    if fund_ids:
        funds_query = funds_query.where(Fund.id.in_(fund_ids))
    funds_result = await session.execute(funds_query)
    funds = funds_result.scalars().all()
    if not funds:
        return []

    fund_id_list = [f.id for f in funds]

    metric_ids = [row.RankingProfileWeight.metric_id for row in weight_rows]
    metrics_result = await session.execute(
        select(FundMetric, MetricDefinition)
        .join(MetricDefinition, FundMetric.metric_id == MetricDefinition.id)
        .where(
            FundMetric.fund_id.in_(fund_id_list),
            FundMetric.metric_id.in_(metric_ids),
        )
        .order_by(FundMetric.extraction_date.desc())
    )
    metrics_rows = metrics_result.all()

    fund_metric_map: dict[uuid.UUID, dict[str, float]] = {f.id: {} for f in funds}
    seen: set[tuple] = set()
    for row in metrics_rows:
        key = (row.FundMetric.fund_id, row.MetricDefinition.key)
        if key not in seen and row.FundMetric.value is not None:
            fund_metric_map[row.FundMetric.fund_id][row.MetricDefinition.key] = float(row.FundMetric.value)
            seen.add(key)

    metric_universe: dict[str, list[float]] = {}
    for fund_id, metrics in fund_metric_map.items():
        for key, val in metrics.items():
            metric_universe.setdefault(key, []).append(val)

    results: list[ScoringResult] = []
    for fund in funds:
        fund_metrics = fund_metric_map[fund.id]
        total = 0.0
        breakdown: dict[str, MetricScoreDetail] = {}
        missing: list[str] = []

        for row in weight_rows:
            metric_def = row.MetricDefinition
            weight = float(row.RankingProfileWeight.weight)
            raw_val = fund_metrics.get(metric_def.key)

            if raw_val is None:
                missing.append(metric_def.key)
                normalized = 0.5
            else:
                all_vals = metric_universe.get(metric_def.key, [raw_val])
                normalized = _normalize(raw_val, metric_def.higher_is_better, all_vals)

            contribution = normalized * weight
            total += contribution
            breakdown[metric_def.key] = MetricScoreDetail(
                raw_value=raw_val,
                normalized_score=round(normalized, 4),
                weight=weight,
                weighted_contribution=round(contribution, 4),
                unit=metric_def.unit or "",
                higher_is_better=metric_def.higher_is_better,
            )

        completeness = 1.0 - (len(missing) / len(weight_rows)) if weight_rows else 0.0
        results.append(ScoringResult(
            fund_id=fund.id,
            total_score=round(total, 4),
            breakdown=breakdown,
            missing_metrics=missing,
            data_completeness=round(completeness, 4),
        ))

    results.sort(key=lambda r: r.total_score, reverse=True)

    now = datetime.now(timezone.utc)
    for rank, result in enumerate(results, start=1):
        breakdown_json = {
            key: {
                "raw_value": d.raw_value,
                "normalized_score": d.normalized_score,
                "weight": d.weight,
                "weighted_contribution": d.weighted_contribution,
                "unit": d.unit,
                "higher_is_better": d.higher_is_better,
            }
            for key, d in result.breakdown.items()
        }
        existing = await session.execute(
            select(FundRankingScore).where(
                FundRankingScore.fund_id == result.fund_id,
                FundRankingScore.profile_id == profile_id,
            )
        )
        score_row = existing.scalar_one_or_none()
        if score_row:
            score_row.total_score = Decimal(str(result.total_score))
            score_row.rank_position = rank
            score_row.score_breakdown = breakdown_json
            score_row.computed_at = now
        else:
            session.add(FundRankingScore(
                fund_id=result.fund_id,
                profile_id=profile_id,
                total_score=Decimal(str(result.total_score)),
                rank_position=rank,
                score_breakdown=breakdown_json,
                computed_at=now,
            ))

    return results


async def get_scores(
    session: AsyncSession,
    profile_id: uuid.UUID,
    force_recompute: bool = False,
) -> list[FundRankingScore]:
    """Return cached scores, recomputing if stale or forced."""
    if not force_recompute:
        stale_check = await session.execute(
            select(func.count(FundRankingScore.id)).where(FundRankingScore.profile_id == profile_id)
        )
        count = stale_check.scalar_one()
        if count > 0:
            result = await session.execute(
                select(FundRankingScore)
                .where(FundRankingScore.profile_id == profile_id)
                .order_by(FundRankingScore.rank_position)
            )
            return result.scalars().all()

    await compute_scores_for_profile(session, profile_id)
    result = await session.execute(
        select(FundRankingScore)
        .where(FundRankingScore.profile_id == profile_id)
        .order_by(FundRankingScore.rank_position)
    )
    return result.scalars().all()
