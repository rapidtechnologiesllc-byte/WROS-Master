import logging
"""S-020/HRMS-0420: add candidate_sla_breaches table

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_sla_breaches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("sla_type", sa.String(50), nullable=False),
        sa.Column("breached_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_sla_breaches_tenant_id", "candidate_sla_breaches", ["tenant_id"])
    op.create_index("ix_candidate_sla_breaches_candidate_id", "candidate_sla_breaches", ["candidate_id"])
    op.create_index("ix_candidate_sla_breaches_conversation_id", "candidate_sla_breaches", ["conversation_id"])


def downgrade():
    op.drop_index("ix_candidate_sla_breaches_conversation_id", table_name="candidate_sla_breaches")
    op.drop_index("ix_candidate_sla_breaches_candidate_id", table_name="candidate_sla_breaches")
    op.drop_index("ix_candidate_sla_breaches_tenant_id", table_name="candidate_sla_breaches")
    op.drop_table("candidate_sla_breaches")
