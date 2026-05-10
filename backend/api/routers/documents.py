"""PDF upload and document management endpoints."""
from __future__ import annotations
import hashlib
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models.document import FundDocument
from api.dependencies import get_current_user
from db.models.user import User
from core.config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    fund_id: Optional[str] = Form(None),
    document_type: Optional[str] = Form("factsheet"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    content_hash = hashlib.sha256(content).hexdigest()
    existing = await db.execute(select(FundDocument).where(FundDocument.content_hash == content_hash))
    duplicate = existing.scalar_one_or_none()
    if duplicate:
        return {
            "document_id": str(duplicate.id),
            "status": duplicate.processing_status,
            "filename": duplicate.filename,
            "duplicate": True,
        }

    os.makedirs(settings.upload_dir, exist_ok=True)
    doc_id = uuid.uuid4()
    storage_path = os.path.join(settings.upload_dir, f"{doc_id}.pdf")
    with open(storage_path, "wb") as f:
        f.write(content)

    doc = FundDocument(
        id=doc_id,
        fund_id=uuid.UUID(fund_id) if fund_id else None,
        filename=file.filename or "upload.pdf",
        storage_path=storage_path,
        mime_type=file.content_type,
        file_size_bytes=len(content),
        document_type=document_type,
        processing_status="pending",
        uploaded_by=user.id,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.flush()

    try:
        from processing.worker import process_document
        process_document.delay(str(doc_id))
    except Exception:
        pass

    return {"document_id": str(doc_id), "status": "pending", "filename": file.filename}


@router.get("")
async def list_documents(
    fund_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(FundDocument).where(FundDocument.uploaded_by == user.id)
    if fund_id:
        query = query.where(FundDocument.fund_id == fund_id)
    query = query.order_by(FundDocument.uploaded_at.desc()).limit(50)
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "fund_id": str(d.fund_id) if d.fund_id else None,
            "status": d.processing_status,
            "factsheet_month": d.factsheet_month,
            "page_count": d.page_count,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{doc_id}")
async def get_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FundDocument).where(FundDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "fund_id": str(doc.fund_id) if doc.fund_id else None,
        "status": doc.processing_status,
        "processing_error": doc.processing_error if doc.processing_status == "failed" else None,
        "factsheet_month": doc.factsheet_month,
        "page_count": doc.page_count,
        "file_size_bytes": doc.file_size_bytes,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
    }


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FundDocument).where(FundDocument.id == doc_id, FundDocument.uploaded_by == user.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
    await db.delete(doc)
    await db.flush()


@router.post("/{doc_id}/reprocess")
async def reprocess_document(doc_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FundDocument).where(FundDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.processing_status = "pending"
    doc.processing_error = None
    await db.flush()
    from processing.worker import process_document
    process_document.delay(str(doc_id))
    return {"message": "Reprocessing queued"}
