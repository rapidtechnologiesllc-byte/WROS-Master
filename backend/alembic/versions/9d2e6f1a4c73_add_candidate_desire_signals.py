import logging
"""add candidate_desire_signals (S-347 Candidate Desire Intelligence Engine)

Revision ID: 9d2e6f1a4c73
Revises: 1f4b7c9e2a83
Create Date: 2026-08-05 00:00:00.000000

Same conventions as candidate_sentiment_log/candidate_skill_tag: Integer
autoincrement PK, String(50) UserID-as-tenant_id, plain String columns
instead of native ENUM/DECIMAL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9d2e6f1a4c73'
down_revision: Union[str, Sequence[str], None] = '1f4b7c9e2a83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'candidate_desire_signals',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('signal_source', sa.String(length=30), nullable=False),
        sa.Column('signal_data', sa.JSON(), nullable=False),
        sa.Column('desire_category', sa.String(length=30), nullable=True),
        sa.Column('desire_direction', sa.String(length=20), nullable=True),
        sa.Column('desire_strength', sa.Float(), nullable=True),
        sa.Column('extracted_insight', sa.Text(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
    )
    op.create_index(
        op.f('ix_candidate_desire_signals_lookup'), 'candidate_desire_signals',
        ['tenant_id', 'candidate_id', 'created_at'], unique=False,
    )
    op.create_index(
        op.f('ix_candidate_desire_signals_unprocessed'), 'candidate_desire_signals', ['processed'], unique=False,
    )
    op.create_index(
        op.f('ix_candidate_desire_signals_tenant_id'), 'candidate_desire_signals', ['tenant_id'], unique=False,
    )
    op.create_index(
        op.f('ix_candidate_desire_signals_candidate_id'), 'candidate_desire_signals', ['candidate_id'], unique=False,
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_candidate_desire_signals_candidate_id'), table_name='candidate_desire_signals')
    op.drop_index(op.f('ix_candidate_desire_signals_tenant_id'), table_name='candidate_desire_signals')
    op.drop_index(op.f('ix_candidate_desire_signals_unprocessed'), table_name='candidate_desire_signals')
    op.drop_index(op.f('ix_candidate_desire_signals_lookup'), table_name='candidate_desire_signals')
    op.drop_table('candidate_desire_signals')
