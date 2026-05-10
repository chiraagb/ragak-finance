"""Add content_hash to fund_documents for duplicate detection

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('fund_documents', sa.Column('content_hash', sa.String(64), nullable=True))
    op.create_index('ix_fund_documents_content_hash', 'fund_documents', ['content_hash'])


def downgrade():
    op.drop_index('ix_fund_documents_content_hash', table_name='fund_documents')
    op.drop_column('fund_documents', 'content_hash')
