"""Add soft-delete support to Jobs table

Revision ID: add_soft_delete_001
Revises:
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = 'add_soft_delete_001'
down_revision = '2_add_clients'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add deleted_at and is_deleted columns to jobs table."""
    # Add soft-delete columns (nullable for backward compatibility)
    op.add_column(
        'jobs',
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='Timestamp when job was soft-deleted')
    )
    op.add_column(
        'jobs',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0', comment='Flag indicating if job is soft-deleted')
    )

    # Add index for efficient filtering of active jobs
    op.create_index(
        op.f('ix_jobs_deleted_at'),
        'jobs',
        ['deleted_at'],
        unique=False
    )
    op.create_index(
        op.f('ix_jobs_is_deleted'),
        'jobs',
        ['is_deleted'],
        unique=False
    )


def downgrade() -> None:
    """Remove soft-delete columns from jobs table."""
    op.drop_index(op.f('ix_jobs_is_deleted'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_deleted_at'), table_name='jobs')
    op.drop_column('jobs', 'is_deleted')
    op.drop_column('jobs', 'deleted_at')
