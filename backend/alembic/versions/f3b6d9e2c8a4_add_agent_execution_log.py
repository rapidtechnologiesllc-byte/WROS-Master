import logging
"""add agent_execution_log table (S-066/HRMS-0466)

Revision ID: f3b6d9e2c8a4
Revises: e7a1c3f9b2d6
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "f3b6d9e2c8a4"
down_revision = "e7a1c3f9b2d6"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "agent_execution_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("candidate_id", sa.String(50), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("action_taken", sa.String(200), nullable=False),
        sa.Column("action_data", sa.JSON(), nullable=True),
        sa.Column("execution_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.UserID"], name="fk_agent_execution_log_tenant_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidateID"], name="fk_agent_execution_log_candidate_id", ondelete="CASCADE"),
    )
    op.create_index("ix_agent_execution_log_tenant_id", "agent_execution_log", ["tenant_id"])
    op.create_index("ix_agent_execution_log_candidate_id", "agent_execution_log", ["candidate_id"])
    op.create_index("ix_agent_execution_log_execution_at", "agent_execution_log", ["execution_at"])

def downgrade():
    op.drop_index("ix_agent_execution_log_execution_at", table_name="agent_execution_log")
    op.drop_index("ix_agent_execution_log_candidate_id", table_name="agent_execution_log")
    op.drop_index("ix_agent_execution_log_tenant_id", table_name="agent_execution_log")
    op.drop_table("agent_execution_log")
