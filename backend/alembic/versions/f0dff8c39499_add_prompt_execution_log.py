import logging
"""S-031/HRMS-0431: add prompt_execution_log table

Revision ID: f0dff8c39499
Revises: 0eb7ca2cdb11
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "f0dff8c39499"
down_revision = "0eb7ca2cdb11"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "prompt_execution_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("template_version", sa.String(20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("response_preview", sa.String(200), nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_execution_log_tenant_id", "prompt_execution_log", ["tenant_id"])
    op.create_index("ix_prompt_execution_log_candidate_id", "prompt_execution_log", ["candidate_id"])
    op.create_index("ix_prompt_execution_log_tenant_candidate_created", "prompt_execution_log", ["tenant_id", "candidate_id", "created_at"])

def downgrade():
    op.drop_index("ix_prompt_execution_log_tenant_candidate_created", table_name="prompt_execution_log")
    op.drop_index("ix_prompt_execution_log_candidate_id", table_name="prompt_execution_log")
    op.drop_index("ix_prompt_execution_log_tenant_id", table_name="prompt_execution_log")
    op.drop_table("prompt_execution_log")
