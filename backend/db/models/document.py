import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, BigInteger, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class FundDocument(Base):
    __tablename__ = "fund_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    document_type: Mapped[Optional[str]] = mapped_column(String(50))
    factsheet_month: Mapped[Optional[str]] = mapped_column(String(7))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    fund: Mapped[Optional["Fund"]] = relationship(back_populates="documents")  # noqa: F821
    uploader: Mapped[Optional["User"]] = relationship(back_populates="fund_documents")  # noqa: F821
    chunks: Mapped[List["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
