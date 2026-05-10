"""Risk analysis node: credit quality + maturity buckets + holdings → risk signals."""
from __future__ import annotations
import uuid
from agents.state import AgentState
from db.models.fund_metric import FundCreditProfile, FundMaturityBucket, FundHolding
from sqlalchemy import select


async def risk_node(state: AgentState, db) -> dict:
    fund_id_strs = state.get("extracted_fund_ids", [])
    fund_ids = [uuid.UUID(fid) for fid in fund_id_strs if fid]
    if not fund_ids:
        return {"risk_data": None}

    risk_data = {}
    for fund_id in fund_ids[:3]:
        fid_str = str(fund_id)

        credit_result = await db.execute(
            select(FundCreditProfile)
            .where(FundCreditProfile.fund_id == fund_id)
            .order_by(FundCreditProfile.as_of_date.desc())
            .limit(10)
        )
        credit_rows = credit_result.scalars().all()

        maturity_result = await db.execute(
            select(FundMaturityBucket)
            .where(FundMaturityBucket.fund_id == fund_id)
            .order_by(FundMaturityBucket.as_of_date.desc())
            .limit(10)
        )
        maturity_rows = maturity_result.scalars().all()

        holdings_result = await db.execute(
            select(FundHolding)
            .where(FundHolding.fund_id == fund_id)
            .order_by(FundHolding.percentage.desc())
            .limit(10)
        )
        holdings_rows = holdings_result.scalars().all()

        credit_summary = {row.rating: float(row.percentage) for row in credit_rows if row.percentage}
        maturity_summary = {row.bucket_name: float(row.percentage) for row in maturity_rows if row.percentage}
        top_holdings = [
            {
                "name": h.instrument_name,
                "issuer": h.issuer_name,
                "rating": h.rating,
                "pct": float(h.percentage) if h.percentage else None,
                "type": h.instrument_type,
            }
            for h in holdings_rows
        ]

        risk_signals = _compute_risk_signals(credit_summary, maturity_summary, top_holdings)
        risk_data[fid_str] = {
            "credit_summary": credit_summary,
            "maturity_summary": maturity_summary,
            "top_holdings": top_holdings,
            "risk_signals": risk_signals,
        }

    return {"risk_data": risk_data}


def _compute_risk_signals(
    credit: dict[str, float],
    maturity: dict[str, float],
    holdings: list[dict],
) -> list[str]:
    signals = []
    aaa = credit.get("AAA", 0) + credit.get("A1+", 0) + credit.get("Sovereign", 0)
    if aaa < 80:
        signals.append(f"⚠ Only {aaa:.1f}% in highest-rated instruments (AAA/Sovereign/A1+)")
    if aaa >= 95:
        signals.append(f"✓ Excellent credit quality — {aaa:.1f}% in AAA/Sovereign/A1+ instruments")

    overnight = maturity.get("Overnight", 0)
    lt7d = overnight + maturity.get("1-7 Days", 0) + maturity.get("7 Days", 0)
    if lt7d < 20:
        signals.append(f"⚠ Only {lt7d:.1f}% maturing within 7 days — moderate liquidity risk")
    if lt7d >= 50:
        signals.append(f"✓ {lt7d:.1f}% matures within 7 days — strong short-term liquidity")

    if holdings:
        max_holding = max((h["pct"] or 0) for h in holdings)
        if max_holding > 10:
            signals.append(f"⚠ Single issuer concentration: top holding is {max_holding:.1f}%")

    return signals
