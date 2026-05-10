import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Date, Numeric, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class FundCategory(Base):
    __tablename__ = "fund_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sebi_code: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    funds: Mapped[List["Fund"]] = relationship(back_populates="category")


class Fund(Base):
    __tablename__ = "funds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isin: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    amfi_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amc_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("fund_categories.id"))
    fund_type: Mapped[Optional[str]] = mapped_column(String(50))
    inception_date: Mapped[Optional[date]] = mapped_column(Date)
    benchmark_index: Mapped[Optional[str]] = mapped_column(String(100))
    fund_manager: Mapped[Optional[str]] = mapped_column(String(200))
    aum_crores: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    expense_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    nav_date: Mapped[Optional[date]] = mapped_column(Date)
    exit_load: Mapped[Optional[str]] = mapped_column(String(200))
    minimum_investment: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    lock_in_period_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    category: Mapped[Optional["FundCategory"]] = relationship(back_populates="funds")
    metrics: Mapped[List["FundMetric"]] = relationship(back_populates="fund", cascade="all, delete-orphan")  # noqa: F821
    documents: Mapped[List["FundDocument"]] = relationship(back_populates="fund")  # noqa: F821
    ranking_scores: Mapped[List["FundRankingScore"]] = relationship(back_populates="fund", cascade="all, delete-orphan")  # noqa: F821
    credit_profile: Mapped[List["FundCreditProfile"]] = relationship(back_populates="fund", cascade="all, delete-orphan")  # noqa: F821
    maturity_buckets: Mapped[List["FundMaturityBucket"]] = relationship(back_populates="fund", cascade="all, delete-orphan")  # noqa: F821
    holdings: Mapped[List["FundHolding"]] = relationship(back_populates="fund", cascade="all, delete-orphan")  # noqa: F821


class FundNavHistory(Base):
    __tablename__ = "fund_nav_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
