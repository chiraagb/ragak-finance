"""Add fund_sector_allocation table and active_fund_ids to chat_sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fund_sector_allocation',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('fund_id', UUID(as_uuid=True), sa.ForeignKey('funds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sector_name', sa.String(200), nullable=False),
        sa.Column('percentage', sa.Numeric(5, 2)),
        sa.Column('as_of_date', sa.Date, nullable=False),
        sa.UniqueConstraint('fund_id', 'sector_name', 'as_of_date', name='uq_sector_fund_date'),
    )
    op.create_index('idx_fund_sector_fund', 'fund_sector_allocation', ['fund_id', 'as_of_date'])

    op.add_column('chat_sessions', sa.Column('active_fund_ids', ARRAY(UUID(as_uuid=True)), nullable=True))


def downgrade():
    op.drop_column('chat_sessions', 'active_fund_ids')
    op.drop_index('idx_fund_sector_fund', table_name='fund_sector_allocation')
    op.drop_table('fund_sector_allocation')
