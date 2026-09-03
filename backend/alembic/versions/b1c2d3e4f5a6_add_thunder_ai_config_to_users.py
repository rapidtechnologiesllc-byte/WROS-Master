import logging
"""S-011/HRMS-0411: add per-tenant Thunder AI config columns to users

Revision ID: b1c2d3e4f5a6
Revises: a4b5c6d7e8f9
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("ai_agent_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("ai_agent_persona", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("users", "ai_agent_persona")
    op.drop_column("users", "ai_agent_name")
