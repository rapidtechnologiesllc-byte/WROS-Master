import logging
"""S-049/HRMS-0449: add confirmed_at column to submission_interviews

Revision ID: 6b1e9d4a83f2
Revises: 2f8b6d4c9a17
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "6b1e9d4a83f2"
down_revision = "2f8b6d4c9a17"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.drop_column("confirmed_at")
