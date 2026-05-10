"""Fetch and import mutual fund data from MFAPI.in."""
from __future__ import annotations
import asyncio
import httpx
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from db.models.fund import Fund, FundCategory

logger = structlog.get_logger()

MFAPI_BASE = "https://api.mfapi.in/mf"

# Category filter keywords -> SEBI category name
CATEGORY_FILTERS = {
    "liquid": "Liquid Fund",
    "money_market": "Money Market Fund",
    "overnight": "Overnight Fund",
    "ultra_short": "Ultra Short Duration Fund",
    "low_duration": "Low Duration Fund",
}


async def fetch_all_schemes(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(MFAPI_BASE, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def fetch_scheme_detail(client: httpx.AsyncClient, scheme_code: int) -> dict | None:
    try:
        resp = await client.get(f"{MFAPI_BASE}/{scheme_code}", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def _fetch_batch(client: httpx.AsyncClient, codes: list[int], semaphore: asyncio.Semaphore) -> list[dict]:
    async def fetch_one(code: int) -> dict | None:
        async with semaphore:
            return await fetch_scheme_detail(client, code)

    results = await asyncio.gather(*[fetch_one(c) for c in codes])
    return [r for r in results if r is not None]


def _parse_nav_date(date_str: str) -> date | None:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


async def import_funds(
    db: AsyncSession,
    categories: list[str] | None = None,
    max_funds: int = 200,
) -> dict:
    """
    Fetch funds from MFAPI.in and upsert into the database.
    categories: list of keys from CATEGORY_FILTERS, or None for all tracked categories.
    Returns {"imported": int, "skipped": int, "errors": int}
    """
    if categories is None:
        categories = list(CATEGORY_FILTERS.keys())

    filter_terms = [CATEGORY_FILTERS[c] for c in categories if c in CATEGORY_FILTERS]

    async with httpx.AsyncClient() as client:
        logger.info("mfapi_fetch_start", categories=categories)
        all_schemes = await fetch_all_schemes(client)

        # Pre-filter by name keywords to reduce detail fetches
        name_keywords = ["liquid", "money market", "overnight", "ultra short", "low duration"]
        if categories == ["liquid"]:
            name_keywords = ["liquid"]

        candidates = [
            s for s in all_schemes
            if any(kw in s["schemeName"].lower() for kw in name_keywords)
            and "direct" in s["schemeName"].lower()
            and "growth" in s["schemeName"].lower()
        ][:max_funds]

        logger.info("mfapi_candidates", count=len(candidates))

        # Fetch details with concurrency cap of 20
        semaphore = asyncio.Semaphore(20)
        details = await _fetch_batch(client, [s["schemeCode"] for s in candidates], semaphore)

    # Filter by actual scheme_category from detail
    if filter_terms:
        details = [
            d for d in details
            if any(ft.lower() in d.get("meta", {}).get("scheme_category", "").lower() for ft in filter_terms)
        ]

    imported = skipped = errors = 0

    # Ensure categories exist
    category_cache: dict[str, FundCategory] = {}

    async def get_or_create_category(sebi_category: str) -> FundCategory:
        if sebi_category in category_cache:
            return category_cache[sebi_category]
        result = await db.execute(select(FundCategory).where(FundCategory.name == sebi_category))
        cat = result.scalar_one_or_none()
        if not cat:
            cat = FundCategory(name=sebi_category)
            db.add(cat)
            await db.flush()
        category_cache[sebi_category] = cat
        return cat

    for detail in details:
        try:
            meta = detail.get("meta", {})
            nav_data = detail.get("data", [])

            scheme_code = str(meta.get("scheme_code", ""))
            scheme_name = meta.get("scheme_name", "").strip()
            fund_house = meta.get("fund_house", "").strip()
            scheme_category = meta.get("scheme_category", "").strip()

            if not scheme_name or not fund_house:
                skipped += 1
                continue

            # Get latest NAV
            latest_nav = None
            latest_nav_date = None
            if nav_data:
                latest = nav_data[0]
                try:
                    latest_nav = Decimal(latest["nav"])
                    latest_nav_date = _parse_nav_date(latest["date"])
                except Exception:
                    pass

            # Check if already exists
            existing = await db.execute(select(Fund).where(Fund.amfi_code == scheme_code))
            fund = existing.scalar_one_or_none()

            category = await get_or_create_category(scheme_category) if scheme_category else None

            if fund:
                # Update NAV only
                if latest_nav:
                    fund.nav = latest_nav
                    fund.nav_date = latest_nav_date
                skipped += 1
            else:
                fund = Fund(
                    name=scheme_name,
                    amc_name=fund_house,
                    amfi_code=scheme_code,
                    nav=latest_nav,
                    nav_date=latest_nav_date,
                    category_id=category.id if category else None,
                    is_active=True,
                    data_source="mfapi",
                )
                db.add(fund)
                imported += 1

        except Exception as e:
            logger.warning("mfapi_fund_error", error=str(e))
            errors += 1

    await db.flush()
    logger.info("mfapi_import_done", imported=imported, skipped=skipped, errors=errors)
    return {"imported": imported, "updated": skipped, "errors": errors}
