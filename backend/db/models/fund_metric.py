import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Boolean, Date, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    higher_is_better: Mapped[bool] = mapped_column(Boolean, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))

    fund_metrics: Mapped[list["FundMetric"]] = relationship(back_populates="metric_definition")
    profile_weights: Mapped[list["RankingProfileWeight"]] = relationship(back_populates="metric_definition")  # noqa: F821


class FundMetric(Base):
    __tablename__ = "fund_metrics"
    __table_args__ = (UniqueConstraint("fund_id", "metric_id", "extraction_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    metric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("metric_definitions.id"), nullable=False)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    extraction_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("fund_documents.id"))
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))

    fund: Mapped["Fund"] = relationship(back_populates="metrics")  # noqa: F821
    metric_definition: Mapped["MetricDefinition"] = relationship(back_populates="fund_metrics")


class FundCreditProfile(Base):
    __tablename__ = "fund_credit_profile"
    __table_args__ = (UniqueConstraint("fund_id", "rating", "as_of_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    fund: Mapped["Fund"] = relationship(back_populates="credit_profile")  # noqa: F821


class FundMaturityBucket(Base):
    __tablename__ = "fund_maturity_buckets"
    __table_args__ = (UniqueConstraint("fund_id", "bucket_name", "as_of_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bucket_days_min: Mapped[Optional[int]] = mapped_column()
    bucket_days_max: Mapped[Optional[int]] = mapped_column()
    percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    fund: Mapped["Fund"] = relationship(back_populates="maturity_buckets")  # noqa: F821


class FundHolding(Base):
    __tablename__ = "fund_holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    instrument_name: Mapped[Optional[str]] = mapped_column(String(255))
    issuer_name: Mapped[Optional[str]] = mapped_column(String(255))
    rating: Mapped[Optional[str]] = mapped_column(String(20))
    maturity_date: Mapped[Optional[date]] = mapped_column(Date)
    percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    instrument_type: Mapped[Optional[str]] = mapped_column(String(100))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    fund: Mapped["Fund"] = relationship(back_populates="holdings")  # noqa: F821
