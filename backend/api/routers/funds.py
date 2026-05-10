"""Fund search, detail, metrics, holdings, credit, maturity endpoints."""
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel

from db.session import get_db
from db.models.fund import Fund, FundCategory
from db.models.fund_metric import MetricDefinition, FundMetric, FundCreditProfile, FundMaturityBucket, FundHolding
from api.dependencies import get_current_user
from db.models.user import User

router = APIRouter(prefix="/api/funds", tags=["funds"])


class FundSummary(BaseModel):
    id: str
    name: str
    amc_name: str
    category: Optional[str]
    aum_crores: Optional[float]
    expense_ratio: Optional[float]
    nav: Optional[float]

class CreateFundRequest(BaseModel):
    name: str
    amc_name: str
    isin: Optional[str] = None
    amfi_code: Optional[str] = None
    category_id: Optional[str] = None
    aum_crores: Optional[float] = None
    expense_ratio: Optional[float] = None
    nav: Optional[float] = None
    fund_manager: Optional[str] = None


@router.get("", response_model=list[FundSummary])
async def list_funds(
    category: Optional[str] = None,
    amc: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Fund, FundCategory).outerjoin(FundCategory, Fund.category_id == FundCategory.id).where(Fund.is_active == True)  # noqa: E712
    if category:
        query = query.where(FundCategory.name.ilike(f"%{category}%"))
    if amc:
        query = query.where(Fund.amc_name.ilike(f"%{amc}%"))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    return [
        FundSummary(
            id=str(r.Fund.id),
            name=r.Fund.name,
            amc_name=r.Fund.amc_name,
            category=r.FundCategory.name if r.FundCategory else None,
            aum_crores=float(r.Fund.aum_crores) if r.Fund.aum_crores else None,
            expense_ratio=float(r.Fund.expense_ratio) if r.Fund.expense_ratio else None,
            nav=float(r.Fund.nav) if r.Fund.nav else None,
        )
        for r in rows
    ]


@router.get("/search")
async def search_funds(q: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    import httpx, json
    from core.config import settings

    cache_key = f"mfapi:search:{q.lower()}"

    # Try Redis cache first
    try:
        import redis as _redis
        r = _redis.from_url(settings.redis_url, decode_responses=True)
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        r = None

    # Live search from MFAPI.in
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.mfapi.in/mf/search?q={q}")
            resp.raise_for_status()
            mfapi_results = resp.json()  # [{schemeCode, schemeName}]
    except Exception:
        mfapi_results = []

    # Merge with local DB to flag funds that have enriched data (metrics, factsheets)
    local_result = await db.execute(
        text("SELECT amfi_code, id FROM funds WHERE is_active = TRUE")
    )
    local_amfi_map = {str(r.amfi_code): str(r.id) for r in local_result.all() if r.amfi_code}

    results = [
        {
            "id": local_amfi_map.get(str(item["schemeCode"]), str(item["schemeCode"])),
            "scheme_code": item["schemeCode"],
            "name": item["schemeName"],
            "amc_name": item["schemeName"].split(" - ")[0] if " - " in item["schemeName"] else "",
            "has_local_data": str(item["schemeCode"]) in local_amfi_map,
        }
        for item in mfapi_results[:15]
    ]

    if r:
        try:
            r.setex(cache_key, 600, json.dumps(results))
        except Exception:
            pass

    return results


@router.get("/{fund_id}")
async def get_fund(fund_id: str, db: AsyncSession = Depends(get_db)):
    import httpx
    from decimal import Decimal
    from datetime import datetime

    # Try local DB first (fund_id may be a UUID or an AMFI scheme code)
    fund = None
    try:
        result = await db.execute(select(Fund).where(Fund.id == uuid.UUID(fund_id)))
        fund = result.scalar_one_or_none()
    except (ValueError, AttributeError):
        pass

    if not fund:
        # Try by amfi_code
        result = await db.execute(select(Fund).where(Fund.amfi_code == fund_id))
        fund = result.scalar_one_or_none()

    if not fund:
        # Auto-fetch from MFAPI.in and create a minimal record
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.mfapi.in/mf/{fund_id}")
                resp.raise_for_status()
                data = resp.json()
            meta = data.get("meta", {})
            nav_data = data.get("data", [])
            latest_nav = Decimal(nav_data[0]["nav"]) if nav_data else None
            nav_date = None
            if nav_data:
                for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        nav_date = datetime.strptime(nav_data[0]["date"], fmt).date()
                        break
                    except ValueError:
                        continue
            fund = Fund(
                name=meta.get("scheme_name", "Unknown"),
                amc_name=meta.get("fund_house", ""),
                amfi_code=str(meta.get("scheme_code", fund_id)),
                nav=latest_nav,
                nav_date=nav_date,
                is_active=True,
                data_source="mfapi",
            )
            db.add(fund)
            await db.flush()
        except Exception:
            raise HTTPException(status_code=404, detail="Fund not found")
    return {
        "id": str(fund.id),
        "name": fund.name,
        "isin": fund.isin,
        "amfi_code": fund.amfi_code,
        "amc_name": fund.amc_name,
        "nav": float(fund.nav) if fund.nav else None,
        "nav_date": fund.nav_date.isoformat() if fund.nav_date else None,
        "aum_crores": float(fund.aum_crores) if fund.aum_crores else None,
        "expense_ratio": float(fund.expense_ratio) if fund.expense_ratio else None,
        "fund_manager": fund.fund_manager,
        "inception_date": fund.inception_date.isoformat() if fund.inception_date else None,
        "benchmark_index": fund.benchmark_index,
        "exit_load": fund.exit_load,
        "lock_in_period_days": fund.lock_in_period_days,
    }


@router.get("/{fund_id}/metrics")
async def get_fund_metrics(fund_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FundMetric, MetricDefinition)
        .join(MetricDefinition, FundMetric.metric_id == MetricDefinition.id)
        .where(FundMetric.fund_id == fund_id)
        .order_by(FundMetric.extraction_date.desc())
    )
    seen: set[str] = set()
    metrics = []
    for row in result.all():
        key = row.MetricDefinition.key
        if key not in seen:
            metrics.append({
                "key": key,
                "display_name": row.MetricDefinition.display_name,
                "value": float(row.FundMetric.value) if row.FundMetric.value else None,
                "unit": row.MetricDefinition.unit,
                "higher_is_better": row.MetricDefinition.higher_is_better,
                "extraction_date": row.FundMetric.extraction_date.isoformat(),
                "confidence": float(row.FundMetric.confidence) if row.FundMetric.confidence else None,
            })
            seen.add(key)
    return metrics


@router.get("/{fund_id}/credit")
async def get_credit_profile(fund_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FundCreditProfile).where(FundCreditProfile.fund_id == fund_id).order_by(FundCreditProfile.as_of_date.desc()).limit(20)
    )
    rows = result.scalars().all()
    return [{"rating": r.rating, "percentage": float(r.percentage) if r.percentage else None, "as_of_date": r.as_of_date.isoformat()} for r in rows]


@router.get("/{fund_id}/maturity")
async def get_maturity_profile(fund_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FundMaturityBucket).where(FundMaturityBucket.fund_id == fund_id).order_by(FundMaturityBucket.as_of_date.desc()).limit(20)
    )
    rows = result.scalars().all()
    return [{"bucket": r.bucket_name, "min_days": r.bucket_days_min, "max_days": r.bucket_days_max, "percentage": float(r.percentage) if r.percentage else None} for r in rows]


@router.get("/{fund_id}/holdings")
async def get_holdings(fund_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FundHolding).where(FundHolding.fund_id == fund_id).order_by(FundHolding.percentage.desc()).limit(20)
    )
    rows = result.scalars().all()
    return [{"name": h.instrument_name, "issuer": h.issuer_name, "rating": h.rating, "pct": float(h.percentage) if h.percentage else None, "type": h.instrument_type} for h in rows]


@router.post("/import/mfapi", status_code=200)
async def import_from_mfapi(
    categories: list[str] = Query(default=["liquid"]),
    max_funds: int = Query(default=200, le=500),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch real fund data from MFAPI.in and import into the database."""
    from processing.mfapi_importer import import_funds
    result = await import_funds(db, categories=categories, max_funds=max_funds)
    await db.commit()
    return result


@router.post("", status_code=201)
async def create_fund(body: CreateFundRequest, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fund = Fund(
        name=body.name,
        amc_name=body.amc_name,
        isin=body.isin,
        amfi_code=body.amfi_code,
        category_id=uuid.UUID(body.category_id) if body.category_id else None,
        aum_crores=body.aum_crores,
        expense_ratio=body.expense_ratio,
        nav=body.nav,
        fund_manager=body.fund_manager,
        data_source="manual",
    )
    db.add(fund)
    await db.flush()
    return {"id": str(fund.id), "name": fund.name}
