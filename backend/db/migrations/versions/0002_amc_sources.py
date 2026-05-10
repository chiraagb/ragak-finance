"""Add amc_sources table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "amc_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("amc_name", sa.String(200), nullable=False),
        sa.Column("factsheet_url", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_status", sa.String(20), nullable=True),
        sa.Column("last_fetch_error", sa.Text, nullable=True),
        sa.Column("last_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_amc_sources_active", "amc_sources", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_amc_sources_active", "amc_sources")
    op.drop_table("amc_sources")
