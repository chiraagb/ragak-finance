"""Seed script: metric definitions + system ranking profiles + live fund import."""
import asyncio
import uuid  # used in seed_metrics return type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from db.session import AsyncSessionLocal
from db.models.fund_metric import MetricDefinition
from db.models.ranking import RankingProfile, RankingProfileWeight

METRIC_DEFINITIONS = [
    {"key": "aaa_pct", "display_name": "AAA / Equivalent %", "unit": "percentage", "higher_is_better": True, "category": "credit"},
    {"key": "sovereign_pct", "display_name": "Sovereign / G-Sec %", "unit": "percentage", "higher_is_better": True, "category": "credit"},
    {"key": "a1plus_pct", "display_name": "A1+ Short-term Rating %", "unit": "percentage", "higher_is_better": True, "category": "credit"},
    {"key": "overnight_bucket_pct", "display_name": "Overnight Maturity %", "unit": "percentage", "higher_is_better": True, "category": "liquidity"},
    {"key": "lt7d_bucket_pct", "display_name": "<7 Days Maturity %", "unit": "percentage", "higher_is_better": True, "category": "liquidity"},
    {"key": "wam_days", "display_name": "Weighted Avg Maturity (days)", "unit": "days", "higher_is_better": False, "category": "liquidity"},
    {"key": "expense_ratio", "display_name": "Expense Ratio", "unit": "percentage", "higher_is_better": False, "category": "cost"},
    {"key": "aum_crores", "display_name": "AUM (Crores)", "unit": "crores", "higher_is_better": True, "category": "size"},
    {"key": "max_single_issuer_pct", "display_name": "Max Single Issuer Exposure %", "unit": "percentage", "higher_is_better": False, "category": "credit"},
    {"key": "returns_1y", "display_name": "1 Year Returns", "unit": "percentage", "higher_is_better": True, "category": "performance"},
    {"key": "returns_3y", "display_name": "3 Year Returns", "unit": "percentage", "higher_is_better": True, "category": "performance"},
]

SYSTEM_PROFILES = [
    {
        "name": "Emergency Fund Conservative",
        "description": "Prioritizes credit quality and short maturity — ideal for emergency funds",
        "weights": {
            "aaa_pct": 0.35,
            "overnight_bucket_pct": 0.20,
            "lt7d_bucket_pct": 0.15,
            "expense_ratio": 0.10,
            "aum_crores": 0.10,
            "wam_days": 0.10,
        },
    },
    {
        "name": "Balanced Liquid",
        "description": "Balances credit quality, returns, and cost",
        "weights": {
            "aaa_pct": 0.25,
            "returns_1y": 0.20,
            "expense_ratio": 0.15,
            "aum_crores": 0.15,
            "lt7d_bucket_pct": 0.15,
            "wam_days": 0.10,
        },
    },
]


async def seed_metrics(session: AsyncSession) -> dict[str, uuid.UUID]:
    metric_id_map: dict[str, uuid.UUID] = {}
    for m in METRIC_DEFINITIONS:
        result = await session.execute(select(MetricDefinition).where(MetricDefinition.key == m["key"]))
        existing = result.scalar_one_or_none()
        if existing:
            metric_id_map[m["key"]] = existing.id
            continue
        metric = MetricDefinition(**m)
        session.add(metric)
        await session.flush()
        metric_id_map[m["key"]] = metric.id
    return metric_id_map


async def seed_profiles(session: AsyncSession, metric_id_map: dict[str, uuid.UUID]) -> None:
    for profile_data in SYSTEM_PROFILES:
        result = await session.execute(
            select(RankingProfile).where(RankingProfile.name == profile_data["name"], RankingProfile.is_system == True)  # noqa: E712
        )
        if result.scalar_one_or_none():
            continue
        profile = RankingProfile(
            name=profile_data["name"],
            description=profile_data["description"],
            is_system=True,
            is_public=True,
        )
        session.add(profile)
        await session.flush()
        for metric_key, weight in profile_data["weights"].items():
            metric_id = metric_id_map.get(metric_key)
            if metric_id:
                session.add(RankingProfileWeight(profile_id=profile.id, metric_id=metric_id, weight=weight))




async def seed_extensions(session: AsyncSession) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


async def run_seed() -> None:
    from processing.mfapi_importer import import_funds
    async with AsyncSessionLocal() as session:
        print("Creating extensions...")
        await seed_extensions(session)
        print("Seeding metric definitions...")
        metric_id_map = await seed_metrics(session)
        print("Seeding system ranking profiles...")
        await seed_profiles(session, metric_id_map)
        await session.commit()

    # Import real funds from MFAPI.in in a fresh session (importer commits internally via flush)
    async with AsyncSessionLocal() as session:
        print("Importing liquid funds from MFAPI.in...")
        result = await import_funds(
            session,
            categories=["liquid", "money_market", "overnight", "ultra_short", "low_duration"],
            max_funds=300,
        )
        await session.commit()
        print(f"MFAPI import done — imported={result['imported']} updated={result['updated']} errors={result['errors']}")
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run_seed())
