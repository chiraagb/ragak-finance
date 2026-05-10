"""Celery tasks for async PDF processing pipeline."""
import asyncio
import uuid
from datetime import datetime, timezone, date
from typing import Optional

import structlog
from celery import Celery
from celery.schedules import crontab
from core.config import settings

logger = structlog.get_logger()

celery_app = Celery("ragak", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"

# Run fetch_all_amc_sources on the 1st of every month at 2am
celery_app.conf.beat_schedule = {
    "fetch-amc-factsheets-monthly": {
        "task": "processing.worker.fetch_all_amc_sources",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),
    }
}
celery_app.conf.timezone = "Asia/Kolkata"


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str):
    """Full ingestion pipeline: PDF → chunks → embeddings → metric extraction."""
    logger.info("process_document_start", document_id=document_id, attempt=self.request.retries)
    try:
        _run_async(_process_document_async(uuid.UUID(document_id)))
        logger.info("process_document_done", document_id=document_id)
    except Exception as exc:
        logger.warning("process_document_failed", document_id=document_id, error=str(exc), attempt=self.request.retries)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _process_document_async(document_id: uuid.UUID):
    from db.session import AsyncSessionLocal
    from db.models.document import FundDocument
    from db.models.chunk import DocumentChunk
    from db.models.fund_metric import MetricDefinition, FundMetric, FundCreditProfile, FundMaturityBucket
    from processing.pdf_extractor import extract_pdf
    from processing.chunker import chunk_pages
    from processing.metric_extractor import extract_metrics_per_scheme
    from processing.embedder import get_embeddings_batch
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FundDocument).where(FundDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.processing_status = "processing"
        await session.commit()

        try:
            logger.info("pdf_extract_start", document_id=str(document_id), path=doc.storage_path)
            pages, detected_fund_name, factsheet_month = extract_pdf(doc.storage_path)
            logger.info("pdf_extract_done", document_id=str(document_id), pages=len(pages), fund=detected_fund_name, month=factsheet_month)

            if factsheet_month and not doc.factsheet_month:
                doc.factsheet_month = factsheet_month

            fund_id = doc.fund_id
            fund_name = detected_fund_name

            if fund_id and not fund_name:
                from db.models.fund import Fund
                fund_result = await session.execute(select(Fund).where(Fund.id == fund_id))
                fund = fund_result.scalar_one_or_none()
                if fund:
                    fund_name = fund.name

            # --- Pass 1: Embed only commentary/strategy sections ---
            chunks = chunk_pages(pages, fund_name=fund_name, factsheet_month=factsheet_month)
            logger.info("chunking_done", document_id=str(document_id), chunks=len(chunks))

            if chunks:
                texts_to_embed = [c.chunk_text for c in chunks]
                embeddings = await get_embeddings_batch(texts_to_embed)
                logger.info("embedding_done", document_id=str(document_id), count=len(embeddings))
                for chunk, embedding in zip(chunks, embeddings):
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        fund_id=fund_id,
                        chunk_index=chunk.chunk_index,
                        chunk_text=chunk.chunk_text,
                        page_number=chunk.page_number,
                        section_type=chunk.section_type,
                        section_heading=chunk.section_heading,
                        contains_table=chunk.contains_table,
                        factsheet_month=factsheet_month,
                        fund_name=chunk.fund_name or fund_name,
                        embedding=embedding,
                    )
                    session.add(db_chunk)

            # --- Pass 2: Extract structured data per scheme ---
            from processing.section_classifier import classify_section
            from processing.structured_extractor import (
                extract_holdings, extract_sector_allocation,
                store_holdings, store_sector_allocation,
            )

            scheme_metrics = extract_metrics_per_scheme(pages, default_fund_name=fund_name)
            logger.info("metric_extract_done", document_id=str(document_id), schemes=len(scheme_metrics))
            today = date.today()

            metric_keys = [
                "aaa_pct", "sovereign_pct", "a1plus_pct", "overnight_bucket_pct",
                "lt7d_bucket_pct", "wam_days", "expense_ratio", "aum_crores",
                "max_single_issuer_pct", "returns_1y", "returns_3y",
            ]
            metric_defs_result = await session.execute(
                select(MetricDefinition).where(MetricDefinition.key.in_(metric_keys))
            )
            metric_defs = {m.key: m for m in metric_defs_result.scalars().all()}

            from db.models.fund import Fund
            from sqlalchemy import func

            for scheme_name, metrics in scheme_metrics.items():
                resolved_fund_id = fund_id
                if scheme_name and scheme_name != fund_name:
                    name_result = await session.execute(
                        select(Fund).where(
                            func.similarity(func.lower(Fund.name), scheme_name.lower()) > 0.4
                        ).order_by(
                            func.similarity(func.lower(Fund.name), scheme_name.lower()).desc()
                        ).limit(1)
                    )
                    matched = name_result.scalar_one_or_none()
                    if matched:
                        resolved_fund_id = matched.id

                if not resolved_fund_id:
                    continue

                metric_fields = {
                    "aaa_pct": metrics.aaa_pct,
                    "sovereign_pct": metrics.sovereign_pct,
                    "a1plus_pct": metrics.a1plus_pct,
                    "overnight_bucket_pct": metrics.overnight_bucket_pct,
                    "lt7d_bucket_pct": metrics.lt7d_bucket_pct,
                    "wam_days": metrics.wam_days,
                    "expense_ratio": metrics.expense_ratio,
                    "aum_crores": metrics.aum_crores,
                    "max_single_issuer_pct": metrics.max_single_issuer_pct,
                    "returns_1y": metrics.returns_1y,
                    "returns_3y": metrics.returns_3y,
                }
                for key, value in metric_fields.items():
                    if value is not None and key in metric_defs:
                        fm = FundMetric(
                            fund_id=resolved_fund_id,
                            metric_id=metric_defs[key].id,
                            value=value,
                            extraction_date=today,
                            source_doc_id=document_id,
                            confidence=0.75,
                        )
                        session.add(fm)

                # Extract and store holdings + sector allocation per scheme
                for page in pages:
                    section_heading = page.text.strip().split('\n')[0][:100] if page.text.strip() else ''
                    section_type = classify_section(section_heading, page.text)
                    if section_type == 'holdings':
                        holdings = extract_holdings(page.text, doc.storage_path, page.page_number)
                        if holdings:
                            await store_holdings(session, resolved_fund_id, holdings, today)
                    elif section_type == 'sector_allocation':
                        sectors = extract_sector_allocation(page.text, doc.storage_path, page.page_number)
                        if sectors:
                            await store_sector_allocation(session, resolved_fund_id, sectors, today)

            doc.processing_status = "done"
            doc.processed_at = datetime.now(timezone.utc)
            doc.page_count = len(pages)
            await session.commit()

        except Exception as e:
            logger.error("process_document_error", document_id=str(document_id), error=str(e))
            doc.processing_status = "failed"
            doc.processing_error = str(e)[:1000]
            await session.commit()
            raise


@celery_app.task(bind=True, max_retries=3, name="processing.worker.fetch_amc_source")
def fetch_amc_source(self, source_id: str):
    """Download factsheet PDF from a user-configured AMC URL and queue it for processing."""
    try:
        _run_async(_fetch_amc_source_async(uuid.UUID(source_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _fetch_amc_source_async(source_id: uuid.UUID):
    import os
    import httpx
    from db.session import AsyncSessionLocal
    from db.models.amc_source import AMCSource
    from db.models.document import FundDocument
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AMCSource).where(AMCSource.id == source_id))
        source = result.scalar_one_or_none()
        if not source:
            return

        source.last_fetch_status = "running"
        await session.commit()

        try:
            logger.info("amc_fetch_start", source_id=str(source_id), amc=source.amc_name, url=source.factsheet_url)
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(source.factsheet_url)
                resp.raise_for_status()
                content = resp.content
            logger.info("amc_fetch_downloaded", source_id=str(source_id), size_mb=round(len(content)/1024/1024, 2))

            if len(content) < 1000:
                raise ValueError("Downloaded file is too small to be a valid PDF")

            os.makedirs(settings.upload_dir, exist_ok=True)
            doc_id = uuid.uuid4()
            filename = f"{source.amc_name.replace(' ', '_')}_factsheet_{date.today().strftime('%Y_%m')}.pdf"
            storage_path = os.path.join(settings.upload_dir, f"{doc_id}.pdf")
            with open(storage_path, "wb") as f:
                f.write(content)

            doc = FundDocument(
                id=doc_id,
                filename=filename,
                storage_path=storage_path,
                mime_type="application/pdf",
                file_size_bytes=len(content),
                document_type="factsheet",
                processing_status="pending",
            )
            session.add(doc)
            await session.flush()

            source.last_fetched_at = datetime.now(timezone.utc)
            source.last_fetch_status = "success"
            source.last_fetch_error = None
            source.last_document_id = doc_id
            await session.commit()

            logger.info("amc_fetch_queued", source_id=str(source_id), document_id=str(doc_id))
            process_document.delay(str(doc_id))

        except Exception as e:
            logger.error("amc_fetch_error", source_id=str(source_id), error=str(e))
            source.last_fetch_status = "failed"
            source.last_fetch_error = str(e)[:500]
            source.last_fetched_at = datetime.now(timezone.utc)
            await session.commit()
            raise


@celery_app.task(name="processing.worker.fetch_all_amc_sources")
def fetch_all_amc_sources():
    """Triggered by Celery Beat monthly — queues a fetch for every active AMC source."""
    _run_async(_fetch_all_amc_sources_async())


async def _fetch_all_amc_sources_async():
    from db.session import AsyncSessionLocal
    from db.models.amc_source import AMCSource
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AMCSource).where(AMCSource.is_active == True))  # noqa: E712
        sources = result.scalars().all()
        for source in sources:
            fetch_amc_source.delay(str(source.id))
