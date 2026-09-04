import logging
"""add candidate_desire_profiles (S-348 Desire Profile Builder)

Revision ID: 3b6d8f2e5a91
Revises: 9d2e6f1a4c73
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3b6d8f2e5a91'
down_revision: Union[str, Sequence[str], None] = '9d2e6f1a4c73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'candidate_desire_profiles',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('top_desire_category', sa.String(length=30), nullable=True),
        sa.Column('top_desire_score', sa.Float(), nullable=True),
        sa.Column('desire_ranking', sa.JSON(), nullable=True),
        sa.Column('primary_fear', sa.String(length=30), nullable=True),
        sa.Column('primary_fear_score', sa.Float(), nullable=True),
        sa.Column('engagement_level', sa.String(length=10), nullable=True),
        sa.Column('has_competing_offer', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('decision_urgency', sa.String(length=10), nullable=True),
        sa.Column('narrative_summary', sa.Text(), nullable=True),
        sa.Column('narrative_updated_at', sa.DateTime(), nullable=True),
        sa.Column('profile_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.UniqueConstraint('candidate_id', name='uq_candidate_desire_profile_per_candidate'),
    )
    op.create_index(op.f('ix_candidate_desire_profiles_tenant_id'), 'candidate_desire_profiles', ['tenant_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_candidate_desire_profiles_tenant_id'), table_name='candidate_desire_profiles')
    op.drop_table('candidate_desire_profiles')
