import logging
"""S-036/HRMS-0436: add candidate_sentiment_log table

Revision ID: 0040e68b0bea
Revises: f0dff8c39499
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0040e68b0bea"
down_revision = "f0dff8c39499"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_sentiment_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=True),
        sa.Column("message_event_id", sa.Integer(), sa.ForeignKey("conversation_events.id"), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=False, server_default="NEUTRAL"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("analyzed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_sentiment_log_tenant_id", "candidate_sentiment_log", ["tenant_id"])
    op.create_index("ix_candidate_sentiment_log_candidate_id", "candidate_sentiment_log", ["candidate_id"])
    op.create_index("ix_candidate_sentiment_log_conversation_id", "candidate_sentiment_log", ["conversation_id"])
    op.create_index("ix_candidate_sentiment_log_trend", "candidate_sentiment_log", ["candidate_id", "analyzed_at"])


def downgrade():
    op.drop_index("ix_candidate_sentiment_log_trend", table_name="candidate_sentiment_log")
    op.drop_index("ix_candidate_sentiment_log_conversation_id", table_name="candidate_sentiment_log")
    op.drop_index("ix_candidate_sentiment_log_candidate_id", table_name="candidate_sentiment_log")
    op.drop_index("ix_candidate_sentiment_log_tenant_id", table_name="candidate_sentiment_log")
    op.drop_table("candidate_sentiment_log")
