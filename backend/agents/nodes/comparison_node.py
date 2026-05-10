"""Comparison node: side-by-side metric comparison for multiple funds."""
from __future__ import annotations
import uuid
from agents.state import AgentState
from db.models.fund import Fund
from db.models.fund_metric import MetricDefinition, FundMetric
from db.models.ranking import FundRankingScore
from sqlalchemy import select


async def comparison_node(state: AgentState, db) -> dict:
    fund_id_strs = state.get("extracted_fund_ids", [])
    fund_ids = [uuid.UUID(fid) for fid in fund_id_strs if fid]
    if len(fund_ids) < 2:
        return {"comparison_data": None}

    funds_result = await db.execute(select(Fund).where(Fund.id.in_(fund_ids)))
    funds = {str(f.id): f for f in funds_result.scalars().all()}

    metric_defs_result = await db.execute(select(MetricDefinition))
    metric_defs = {str(m.id): m for m in metric_defs_result.scalars().all()}

    metrics_result = await db.execute(
        select(FundMetric)
        .where(FundMetric.fund_id.in_(fund_ids))
        .order_by(FundMetric.extraction_date.desc())
    )
    metrics_rows = metrics_result.scalars().all()

    fund_metrics: dict[str, dict[str, float]] = {fid_str: {} for fid_str in [str(f) for f in fund_ids]}
    seen: set[tuple] = set()
    for m in metrics_rows:
        key = (str(m.fund_id), str(m.metric_id))
        if key not in seen and m.value is not None:
            metric_key = metric_defs.get(str(m.metric_id))
            if metric_key:
                fund_metrics[str(m.fund_id)][metric_key.key] = float(m.value)
            seen.add(key)

    comparison_table = {}
    for metric_id_str, mdef in metric_defs.items():
        row = {}
        for fid in fund_ids:
            row[str(fid)] = fund_metrics.get(str(fid), {}).get(mdef.key)
        if any(v is not None for v in row.values()):
            comparison_table[mdef.key] = {
                "display_name": mdef.display_name,
                "unit": mdef.unit,
                "higher_is_better": mdef.higher_is_better,
                "values": row,
            }

    winner_per_metric: dict[str, str | None] = {}
    for metric_key, data in comparison_table.items():
        values = {fid: v for fid, v in data["values"].items() if v is not None}
        if len(values) >= 2:
            if data["higher_is_better"]:
                winner = max(values, key=lambda x: values[x])
            else:
                winner = min(values, key=lambda x: values[x])
            winner_per_metric[metric_key] = winner

    profile_id_str = state.get("active_profile_id")
    rank_scores = {}
    if profile_id_str:
        scores_result = await db.execute(
            select(FundRankingScore)
            .where(
                FundRankingScore.fund_id.in_(fund_ids),
                FundRankingScore.profile_id == uuid.UUID(profile_id_str),
            )
        )
        for s in scores_result.scalars().all():
            rank_scores[str(s.fund_id)] = {
                "rank": s.rank_position,
                "total_score": float(s.total_score) if s.total_score else 0.0,
                "breakdown": s.score_breakdown or {},
            }

    return {
        "comparison_data": {
            "fund_ids": [str(f) for f in fund_ids],
            "fund_names": {str(fid): funds[str(fid)].name for fid in fund_ids if str(fid) in funds},
            "comparison_table": comparison_table,
            "winner_per_metric": winner_per_metric,
            "rank_scores": rank_scores,
        }
    }
