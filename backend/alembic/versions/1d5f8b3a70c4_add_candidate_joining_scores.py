import logging
"""S-058/HRMS-0458: add candidate_joining_scores table

Revision ID: 1d5f8b3a70c4
Revises: 4c8d1e6a92f7
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "1d5f8b3a70c4"
down_revision = "4c8d1e6a92f7"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_joining_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("offer_letters.id"), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=False),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "candidate_id", "offer_id", name="uq_candidate_joining_score"),
    )
    op.create_index("ix_candidate_joining_scores_tenant_id", "candidate_joining_scores", ["tenant_id"])
    op.create_index("ix_candidate_joining_scores_candidate_id", "candidate_joining_scores", ["candidate_id"])
    op.create_index("ix_candidate_joining_scores_offer_id", "candidate_joining_scores", ["offer_id"])

def downgrade():
    op.drop_index("ix_candidate_joining_scores_offer_id", table_name="candidate_joining_scores")
    op.drop_index("ix_candidate_joining_scores_candidate_id", table_name="candidate_joining_scores")
    op.drop_index("ix_candidate_joining_scores_tenant_id", table_name="candidate_joining_scores")
    op.drop_table("candidate_joining_scores")
