import logging
"""S-019/HRMS-0419: add summary_generated_at to candidate_conversations

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_conversations", sa.Column("summary_generated_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("candidate_conversations", "summary_generated_at")
