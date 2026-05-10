"""Extracts structured financial data from classified sections and writes to DB tables.

Does NOT embed anything — all output goes directly to PostgreSQL tables.
Uses Camelot for table parsing (falls back to regex on failure).
"""
from __future__ import annotations
import re
import uuid
from datetime import date
from typing import Optional

import structlog

logger = structlog.get_logger()


def _try_camelot(pdf_path: str, page_num: int) -> list[list[str]]:
    """Extract table rows from a PDF page using Camelot. Returns [] on any failure."""
    try:
        import camelot
        tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor='lattice', suppress_stdout=True)
        if not tables or tables.n == 0:
            tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor='stream', suppress_stdout=True)
        rows: list[list[str]] = []
        for table in tables:
            for row in table.df.values.tolist():
                clean = [str(c).strip() for c in row if str(c).strip()]
                if clean:
                    rows.append(clean)
        return rows
    except Exception:
        return []


def _pct(text: str, *patterns: str) -> Optional[float]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (IndexError, ValueError):
                pass
    return None


def extract_holdings(page_text: str, pdf_path: Optional[str], page_num: int) -> list[dict]:
    """Parse holdings table rows. Returns list of {instrument_name, sector, percentage, instrument_type}."""
    rows: list[list[str]] = []
    if pdf_path:
        rows = _try_camelot(pdf_path, page_num)

    holdings = []
    if rows:
        for row in rows:
            if len(row) < 2:
                continue
            name = row[0]
            pct_val = None
            sector = None
            instrument_type = None
            for cell in row[1:]:
                if pct_val is None:
                    m = re.search(r'([\d.]+)\s*%?$', cell)
                    if m:
                        try:
                            v = float(m.group(1))
                            if 0 < v <= 100:
                                pct_val = v
                        except ValueError:
                            pass
                if cell.strip() and not re.search(r'^[\d.%]+$', cell.strip()):
                    if sector is None and len(cell) > 2:
                        sector = cell.strip()
            if name and pct_val is not None and len(name) > 2:
                holdings.append({
                    'instrument_name': name,
                    'sector': sector,
                    'percentage': pct_val,
                    'instrument_type': instrument_type,
                })
        return holdings

    # Regex fallback for text-based holdings
    lines = page_text.split('\n')
    for line in lines:
        m = re.match(r'^(.{5,60}?)\s+([\d.]+)\s*%?\s*$', line.strip())
        if m:
            try:
                pct_val = float(m.group(2))
                if 0 < pct_val <= 100:
                    holdings.append({'instrument_name': m.group(1).strip(), 'sector': None, 'percentage': pct_val, 'instrument_type': None})
            except ValueError:
                pass
    return holdings


def extract_sector_allocation(page_text: str, pdf_path: Optional[str], page_num: int) -> list[dict]:
    """Parse sector allocation table rows. Returns list of {sector_name, percentage}."""
    rows: list[list[str]] = []
    if pdf_path:
        rows = _try_camelot(pdf_path, page_num)

    sectors = []
    if rows:
        for row in rows:
            if len(row) < 2:
                continue
            sector_name = row[0].strip()
            pct_val = None
            for cell in row[1:]:
                m = re.search(r'([\d.]+)', cell)
                if m:
                    try:
                        v = float(m.group(1))
                        if 0 < v <= 100:
                            pct_val = v
                            break
                    except ValueError:
                        pass
            if sector_name and pct_val is not None and len(sector_name) > 2:
                sectors.append({'sector_name': sector_name, 'percentage': pct_val})
        if sectors:
            return sectors

    # Regex fallback
    lines = page_text.split('\n')
    for line in lines:
        m = re.match(r'^(.{3,50}?)\s+([\d.]+)\s*%?\s*$', line.strip())
        if m:
            try:
                pct_val = float(m.group(2))
                if 0 < pct_val <= 100:
                    sectors.append({'sector_name': m.group(1).strip(), 'percentage': pct_val})
            except ValueError:
                pass
    return sectors


async def store_holdings(session, fund_id: uuid.UUID, holdings: list[dict], as_of_date: date):
    from db.models.fund_metric import FundHolding
    from sqlalchemy import select

    if not holdings or not fund_id:
        return
    existing = await session.execute(
        select(FundHolding).where(FundHolding.fund_id == fund_id, FundHolding.as_of_date == as_of_date)
    )
    if existing.scalars().first():
        return  # already stored for this month

    for h in holdings:
        session.add(FundHolding(
            fund_id=fund_id,
            instrument_name=h.get('instrument_name'),
            issuer_name=h.get('issuer_name') or h.get('sector'),
            rating=h.get('rating'),
            percentage=h.get('percentage'),
            instrument_type=h.get('instrument_type'),
            as_of_date=as_of_date,
        ))


async def store_sector_allocation(session, fund_id: uuid.UUID, sectors: list[dict], as_of_date: date):
    from db.models.fund import FundSectorAllocation
    from sqlalchemy import select

    if not sectors or not fund_id:
        return
    existing = await session.execute(
        select(FundSectorAllocation).where(
            FundSectorAllocation.fund_id == fund_id,
            FundSectorAllocation.as_of_date == as_of_date,
        )
    )
    if existing.scalars().first():
        return

    for s in sectors:
        session.add(FundSectorAllocation(
            fund_id=fund_id,
            sector_name=s['sector_name'],
            percentage=s['percentage'],
            as_of_date=as_of_date,
        ))
