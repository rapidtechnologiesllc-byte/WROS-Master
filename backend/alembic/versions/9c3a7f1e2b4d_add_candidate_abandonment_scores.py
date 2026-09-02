import logging
"""S-046/HRMS-0446: add candidate_abandonment_scores table

Revision ID: 9c3a7f1e2b4d
Revises: 7de1b26d9e23
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa

revision = "9c3a7f1e2b4d"
down_revision = "7de1b26d9e23"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_abandonment_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("abandonment_score", sa.Integer(), nullable=False),
        sa.Column("score_components", sa.JSON(), nullable=True),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_abandonment_scores"),
    )
    op.create_index("ix_candidate_abandonment_scores_tenant_id", "candidate_abandonment_scores", ["tenant_id"])
    op.create_index("ix_candidate_abandonment_scores_candidate_id", "candidate_abandonment_scores", ["candidate_id"])
    op.create_index("ix_candidate_abandonment_scores_conversation_id", "candidate_abandonment_scores", ["conversation_id"])


def downgrade():
    op.drop_index("ix_candidate_abandonment_scores_conversation_id", table_name="candidate_abandonment_scores")
    op.drop_index("ix_candidate_abandonment_scores_candidate_id", table_name="candidate_abandonment_scores")
    op.drop_index("ix_candidate_abandonment_scores_tenant_id", table_name="candidate_abandonment_scores")
    op.drop_table("candidate_abandonment_scores")
