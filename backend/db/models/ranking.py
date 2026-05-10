import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Boolean, Numeric, Text, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base


class RankingProfile(Base):
    __tablename__ = "ranking_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    scoring_model: Mapped[str] = mapped_column(String(50), default="weighted_sum")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner: Mapped[Optional["User"]] = relationship(back_populates="ranking_profiles")  # noqa: F821
    weights: Mapped[List["RankingProfileWeight"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    scores: Mapped[List["FundRankingScore"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship(back_populates="active_profile")  # noqa: F821


class RankingProfileWeight(Base):
    __tablename__ = "ranking_profile_weights"
    __table_args__ = (UniqueConstraint("profile_id", "metric_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ranking_profiles.id", ondelete="CASCADE"), nullable=False)
    metric_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("metric_definitions.id"), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    profile: Mapped["RankingProfile"] = relationship(back_populates="weights")
    metric_definition: Mapped["MetricDefinition"] = relationship(back_populates="profile_weights")  # noqa: F821


class FundRankingScore(Base):
    __tablename__ = "fund_ranking_scores"
    __table_args__ = (
        UniqueConstraint("fund_id", "profile_id"),
        Index("idx_ranking_scores_profile", "profile_id", "total_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fund_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ranking_profiles.id", ondelete="CASCADE"), nullable=False)
    total_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    rank_position: Mapped[Optional[int]] = mapped_column(Integer)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    fund: Mapped["Fund"] = relationship(back_populates="ranking_scores")  # noqa: F821
    profile: Mapped["RankingProfile"] = relationship(back_populates="scores")
