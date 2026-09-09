"""Add tenant_id field to Candidate model

Revision ID: f9c1e4f5g7h9
Revises: f8a9b0c1d2e3
Create Date: 2026-09-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9c1e4f5g7h9'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tenant_id column to candidates table
    op.add_column('candidates', sa.Column('tenant_id', sa.Integer(), server_default='1', nullable=False))

    # Create index for tenant_id for efficient querying
    op.create_index('ix_candidates_tenant_id', 'candidates', ['tenant_id'])


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_candidates_tenant_id', table_name='candidates')

    # Remove column
    op.drop_column('candidates', 'tenant_id')
