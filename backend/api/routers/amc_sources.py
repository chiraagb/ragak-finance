"""AMC factsheet source management — CRUD + trigger fetch."""
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl

from db.session import get_db
from db.models.amc_source import AMCSource
from api.dependencies import get_current_user
from db.models.user import User

router = APIRouter(prefix="/api/amc-sources", tags=["amc-sources"])


class CreateAMCSourceRequest(BaseModel):
    amc_name: str
    factsheet_url: str


class UpdateAMCSourceRequest(BaseModel):
    amc_name: Optional[str] = None
    factsheet_url: Optional[str] = None
    is_active: Optional[bool] = None


def _serialize(s: AMCSource) -> dict:
    return {
        "id": str(s.id),
        "amc_name": s.amc_name,
        "factsheet_url": s.factsheet_url,
        "is_active": s.is_active,
        "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        "last_fetch_status": s.last_fetch_status,
        "last_fetch_error": s.last_fetch_error,
        "last_document_id": str(s.last_document_id) if s.last_document_id else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def list_sources(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(AMCSource).order_by(AMCSource.created_at.desc()))
    return [_serialize(s) for s in result.scalars().all()]


@router.post("", status_code=201)
async def create_source(
    body: CreateAMCSourceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    source = AMCSource(
        amc_name=body.amc_name,
        factsheet_url=body.factsheet_url,
        created_by=user.id,
    )
    db.add(source)
    await db.flush()
    await db.commit()
    await db.refresh(source)
    return _serialize(source)


@router.patch("/{source_id}")
async def update_source(
    source_id: uuid.UUID,
    body: UpdateAMCSourceRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AMCSource).where(AMCSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if body.amc_name is not None:
        source.amc_name = body.amc_name
    if body.factsheet_url is not None:
        source.factsheet_url = body.factsheet_url
    if body.is_active is not None:
        source.is_active = body.is_active
    await db.commit()
    await db.refresh(source)
    return _serialize(source)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AMCSource).where(AMCSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()


@router.post("/{source_id}/fetch", status_code=202)
async def trigger_fetch(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AMCSource).where(AMCSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    from processing.worker import fetch_amc_source
    fetch_amc_source.delay(str(source_id))
    return {"message": "Fetch queued", "source_id": str(source_id)}


@router.post("/fetch-all", status_code=202)
async def trigger_fetch_all(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AMCSource).where(AMCSource.is_active == True))  # noqa: E712
    sources = result.scalars().all()
    from processing.worker import fetch_amc_source
    for source in sources:
        fetch_amc_source.delay(str(source.id))
    return {"message": f"Queued {len(sources)} sources"}
