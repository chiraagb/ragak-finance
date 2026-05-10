"""Initial schema — all tables + pgvector + pg_trgm

Revision ID: 0001
Revises:
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("role", sa.String(20), default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fund_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("sebi_code", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "funds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("isin", sa.String(20), unique=True),
        sa.Column("amfi_code", sa.String(20), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("amc_name", sa.String(100), nullable=False),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("fund_categories.id")),
        sa.Column("fund_type", sa.String(50)),
        sa.Column("inception_date", sa.Date),
        sa.Column("benchmark_index", sa.String(100)),
        sa.Column("fund_manager", sa.String(200)),
        sa.Column("aum_crores", sa.Numeric(14, 2)),
        sa.Column("expense_ratio", sa.Numeric(5, 4)),
        sa.Column("nav", sa.Numeric(14, 4)),
        sa.Column("nav_date", sa.Date),
        sa.Column("exit_load", sa.String(200)),
        sa.Column("minimum_investment", sa.Numeric(12, 2)),
        sa.Column("lock_in_period_days", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("data_source", sa.String(50)),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fund_nav_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nav_date", sa.Date, nullable=False),
        sa.Column("nav", sa.Numeric(14, 4), nullable=False),
        sa.UniqueConstraint("fund_id", "nav_date"),
    )
    op.create_index("idx_nav_history_fund_date", "fund_nav_history", ["fund_id", "nav_date"])

    op.create_table(
        "metric_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("unit", sa.String(50)),
        sa.Column("higher_is_better", sa.Boolean, nullable=False),
        sa.Column("category", sa.String(50)),
    )

    op.create_table(
        "fund_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="SET NULL")),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("page_count", sa.Integer),
        sa.Column("document_type", sa.String(50)),
        sa.Column("factsheet_month", sa.String(7)),
        sa.Column("processing_status", sa.String(20), default="pending"),
        sa.Column("processing_error", sa.Text),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "fund_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_id", UUID(as_uuid=True), sa.ForeignKey("metric_definitions.id"), nullable=False),
        sa.Column("value", sa.Numeric(14, 4)),
        sa.Column("raw_text", sa.Text),
        sa.Column("extraction_date", sa.Date, nullable=False),
        sa.Column("source_doc_id", UUID(as_uuid=True), sa.ForeignKey("fund_documents.id")),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.UniqueConstraint("fund_id", "metric_id", "extraction_date"),
    )
    op.create_index("idx_fund_metrics_fund", "fund_metrics", ["fund_id"])
    op.create_index("idx_fund_metrics_metric", "fund_metrics", ["metric_id"])

    op.create_table(
        "fund_credit_profile",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2)),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.UniqueConstraint("fund_id", "rating", "as_of_date"),
    )

    op.create_table(
        "fund_maturity_buckets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_name", sa.String(100), nullable=False),
        sa.Column("bucket_days_min", sa.Integer),
        sa.Column("bucket_days_max", sa.Integer),
        sa.Column("percentage", sa.Numeric(5, 2)),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.UniqueConstraint("fund_id", "bucket_name", "as_of_date"),
    )

    op.create_table(
        "fund_holdings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_name", sa.String(255)),
        sa.Column("issuer_name", sa.String(255)),
        sa.Column("rating", sa.String(20)),
        sa.Column("maturity_date", sa.Date),
        sa.Column("percentage", sa.Numeric(5, 2)),
        sa.Column("instrument_type", sa.String(100)),
        sa.Column("as_of_date", sa.Date, nullable=False),
    )
    op.create_index("idx_fund_holdings_fund", "fund_holdings", ["fund_id", "as_of_date"])

    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("fund_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id")),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("page_number", sa.Integer),
        sa.Column("section_type", sa.String(100)),
        sa.Column("section_heading", sa.String(500)),
        sa.Column("contains_table", sa.Boolean, default=False),
        sa.Column("factsheet_month", sa.String(7)),
        sa.Column("amc_name", sa.String(100)),
        sa.Column("fund_name", sa.String(255)),
        sa.Column("embedding", sa.Text),  # handled as vector via raw SQL below
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    # Add vector column properly — SQLAlchemy column type Text above is a placeholder
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    op.execute("""
        CREATE INDEX idx_chunks_embedding ON document_chunks
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)
    op.execute("""
        CREATE INDEX idx_chunks_text ON document_chunks
        USING gin(to_tsvector('english', chunk_text))
    """)
    op.create_index("idx_chunks_fund", "document_chunks", ["fund_id"])
    op.create_index("idx_chunks_section", "document_chunks", ["section_type"])

    op.create_table(
        "ranking_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("is_system", sa.Boolean, default=False),
        sa.Column("is_public", sa.Boolean, default=False),
        sa.Column("scoring_model", sa.String(50), default="weighted_sum"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "name"),
    )

    op.create_table(
        "ranking_profile_weights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("ranking_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_id", UUID(as_uuid=True), sa.ForeignKey("metric_definitions.id"), nullable=False),
        sa.Column("weight", sa.Numeric(5, 4), nullable=False),
        sa.UniqueConstraint("profile_id", "metric_id"),
    )

    op.create_table(
        "fund_ranking_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fund_id", UUID(as_uuid=True), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("ranking_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_score", sa.Numeric(6, 4)),
        sa.Column("rank_position", sa.Integer),
        sa.Column("score_breakdown", JSONB),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("fund_id", "profile_id"),
    )
    op.create_index("idx_ranking_scores_profile", "fund_ranking_scores", ["profile_id", "total_score"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("session_name", sa.String(500)),
        sa.Column("langgraph_thread_id", sa.String(200), unique=True),
        sa.Column("active_profile_id", UUID(as_uuid=True), sa.ForeignKey("ranking_profiles.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_calls", JSONB),
        sa.Column("intent", sa.String(100)),
        sa.Column("funds_referenced", ARRAY(UUID(as_uuid=True))),
        sa.Column("confidence", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id", "created_at"])

    op.create_table(
        "tool_call_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id")),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("chat_messages.id")),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input_args", JSONB),
        sa.Column("output_summary", JSONB),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "tool_call_logs", "chat_messages", "chat_sessions",
        "fund_ranking_scores", "ranking_profile_weights", "ranking_profiles",
        "document_chunks", "fund_holdings", "fund_maturity_buckets",
        "fund_credit_profile", "fund_metrics", "fund_documents",
        "metric_definitions", "fund_nav_history", "funds", "fund_categories", "users",
    ]:
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
