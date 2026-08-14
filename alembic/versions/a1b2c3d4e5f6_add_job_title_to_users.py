"""Add job_title column to users table

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-08-13 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add job_title column to users table
    op.add_column('users', sa.Column('job_title', sa.String(150), nullable=True))


def downgrade():
    # Remove job_title column from users table
    op.drop_column('users', 'job_title')
