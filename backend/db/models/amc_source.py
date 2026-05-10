"""AMC factsheet source — user-configured URLs the scraper downloads monthly."""
from __future__ import annotations
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class AMCSource(Base):
    __tablename__ = "amc_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amc_name = Column(String(200), nullable=False)
    factsheet_url = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    last_fetch_status = Column(String(20), nullable=True)   # success / failed / running
    last_fetch_error = Column(Text, nullable=True)
    last_document_id = Column(UUID(as_uuid=True), nullable=True)  # most recent FundDocument created

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
