import logging
"""add tenant_id to candidates and jobs

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-20 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('candidates', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_candidates_tenant_id'), 'candidates', ['tenant_id'], unique=False)
    op.create_foreign_key(None, 'candidates', 'tenants', ['tenant_id'], ['id'])

    op.add_column('jobs', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_jobs_tenant_id'), 'jobs', ['tenant_id'], unique=False)
    op.create_foreign_key(None, 'jobs', 'tenants', ['tenant_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'jobs', type_='foreignkey')
    op.drop_index(op.f('ix_jobs_tenant_id'), table_name='jobs')
    op.drop_column('jobs', 'tenant_id')

    op.drop_constraint(None, 'candidates', type_='foreignkey')
    op.drop_index(op.f('ix_candidates_tenant_id'), table_name='candidates')
    op.drop_column('candidates', 'tenant_id')
