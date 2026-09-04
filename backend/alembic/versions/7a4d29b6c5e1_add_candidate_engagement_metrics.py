import logging
"""S-070/HRMS-0470: add candidate_engagement_metrics table

Revision ID: 7a4d29b6c5e1
Revises: 5e91c3d4a8f7
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7a4d29b6c5e1"
down_revision = "5e91c3d4a8f7"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_engagement_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("response_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("avg_response_time_minutes", sa.Integer(), nullable=True),
        sa.Column("total_messages_exchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_to_qualification", sa.Integer(), nullable=True),
        sa.Column("avg_sentiment_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(), nullable=True),
        sa.Column("metrics_calculated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_engagement_metrics"),
    )
    op.create_index("ix_candidate_engagement_metrics_tenant_id", "candidate_engagement_metrics", ["tenant_id"])
    op.create_index("ix_candidate_engagement_metrics_candidate_id", "candidate_engagement_metrics", ["candidate_id"])

def downgrade():
    op.drop_index("ix_candidate_engagement_metrics_candidate_id", table_name="candidate_engagement_metrics")
    op.drop_index("ix_candidate_engagement_metrics_tenant_id", table_name="candidate_engagement_metrics")
    op.drop_table("candidate_engagement_metrics")
