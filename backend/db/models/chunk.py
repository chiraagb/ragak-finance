import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from db.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("idx_chunks_fund", "fund_id"),
        Index("idx_chunks_section", "section_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fund_documents.id", ondelete="CASCADE"), nullable=False)
    fund_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_type: Mapped[Optional[str]] = mapped_column(String(100))
    section_heading: Mapped[Optional[str]] = mapped_column(String(500))
    contains_table: Mapped[bool] = mapped_column(Boolean, default=False)
    factsheet_month: Mapped[Optional[str]] = mapped_column(String(7))
    amc_name: Mapped[Optional[str]] = mapped_column(String(100))
    fund_name: Mapped[Optional[str]] = mapped_column(String(255))
    # 1536 dims for OpenAI text-embedding-3-small
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document: Mapped["FundDocument"] = relationship(back_populates="chunks")  # noqa: F821
