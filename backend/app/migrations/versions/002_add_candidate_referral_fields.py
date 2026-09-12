"""Add referral and audit fields to candidate model.

Revision ID: 002_add_referral_fields
Revises:
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '002_add_referral_fields'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Add columns for referral tracking and creation audit."""
    # Add referral_id FK (nullable for backwards compatibility)
    op.add_column('candidates',
        sa.Column('referral_id', sa.String(512), nullable=True)
    )
    op.create_foreign_key(
        'fk_candidate_referral',
        'candidates', 'employee_referrals',
        ['referral_id'], ['referral_id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_candidate_referral_id', 'candidates', ['referral_id'])

    # Add creation audit fields
    op.add_column('candidates',
        sa.Column('created_by_user_id', sa.String(512), nullable=True)
    )
    op.create_index('ix_candidate_created_by_user_id', 'candidates', ['created_by_user_id'])

    op.add_column('candidates',
        sa.Column('created_by_name', sa.String(512), nullable=True)
    )

    op.add_column('candidates',
        sa.Column('recruitment_source', sa.String(512), nullable=True)
    )
    op.create_index('ix_candidate_recruitment_source', 'candidates', ['recruitment_source'])

def downgrade():
    """Reverse migration."""
    op.drop_index('ix_candidate_recruitment_source', 'candidates')
    op.drop_index('ix_candidate_created_by_user_id', 'candidates')
    op.drop_index('ix_candidate_referral_id', 'candidates')
    op.drop_constraint('fk_candidate_referral', 'candidates', type_='foreignkey')
    op.drop_column('candidates', 'recruitment_source')
    op.drop_column('candidates', 'created_by_name')
    op.drop_column('candidates', 'created_by_user_id')
    op.drop_column('candidates', 'referral_id')
