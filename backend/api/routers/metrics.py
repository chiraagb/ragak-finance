"""Metric definitions endpoint — returns all scoreable metrics."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models.fund_metric import MetricDefinition

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/definitions")
async def list_metric_definitions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MetricDefinition).order_by(MetricDefinition.category, MetricDefinition.key))
    defs = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "key": m.key,
            "display_name": m.display_name,
            "unit": m.unit,
            "higher_is_better": m.higher_is_better,
            "category": m.category,
        }
        for m in defs
    ]
