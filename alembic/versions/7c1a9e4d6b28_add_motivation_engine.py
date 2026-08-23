"""add motivation_content_library + motivation_outcomes (S-349 Proactive Motivation Engine)

Revision ID: 7c1a9e4d6b28
Revises: 3b6d8f2e5a91
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c1a9e4d6b28'
down_revision: Union[str, Sequence[str], None] = '3b6d8f2e5a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'motivation_content_library',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('desire_category', sa.String(length=30), nullable=False),
        sa.Column('content_items', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.UserID']),
        sa.UniqueConstraint('tenant_id', 'desire_category', name='uq_motivation_content_per_tenant_category'),
    )
    op.create_index(op.f('ix_motivation_content_library_tenant_id'), 'motivation_content_library', ['tenant_id'], unique=False)

    op.create_table(
        'motivation_outcomes',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('trigger_type', sa.String(length=30), nullable=False),
        sa.Column('message_sent', sa.Text(), nullable=False),
        sa.Column('desire_category_targeted', sa.String(length=30), nullable=True),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('response_within_24h', sa.Boolean(), nullable=True),
        sa.Column('engagement_before', sa.String(length=10), nullable=True),
        sa.Column('engagement_after', sa.String(length=10), nullable=True),
        sa.Column('offer_accepted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
    )
    op.create_index(op.f('ix_motivation_outcomes_tenant_id'), 'motivation_outcomes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_motivation_outcomes_candidate_id'), 'motivation_outcomes', ['candidate_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_motivation_outcomes_candidate_id'), table_name='motivation_outcomes')
    op.drop_index(op.f('ix_motivation_outcomes_tenant_id'), table_name='motivation_outcomes')
    op.drop_table('motivation_outcomes')
    op.drop_index(op.f('ix_motivation_content_library_tenant_id'), table_name='motivation_content_library')
    op.drop_table('motivation_content_library')
