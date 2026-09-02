import logging
"""S-041/HRMS-0441 + S-042/HRMS-0442: add follow_up_schedule and candidate_no_response_log

Revision ID: 84838a711e64
Revises: 4d8cb154d0b8
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "84838a711e64"
down_revision = "4d8cb154d0b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "follow_up_schedule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("follow_up_number", sa.Integer(), nullable=False),
        sa.Column("triggered_by_message_id", sa.Integer(), sa.ForeignKey("conversation_events.id"), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_follow_up_schedule_tenant_id", "follow_up_schedule", ["tenant_id"])
    op.create_index("ix_follow_up_schedule_candidate_id", "follow_up_schedule", ["candidate_id"])
    op.create_index("ix_follow_up_schedule_conversation_id", "follow_up_schedule", ["conversation_id"])
    op.create_index("ix_follow_up_schedule_job_queue", "follow_up_schedule", ["tenant_id", "scheduled_at", "status"])

    op.create_table(
        "candidate_no_response_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("last_outbound_message_id", sa.Integer(), sa.ForeignKey("conversation_events.id"), nullable=True),
        sa.Column("detection_type", sa.String(20), nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("follow_up_scheduled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_candidate_no_response_log_tenant_id", "candidate_no_response_log", ["tenant_id"])
    op.create_index("ix_candidate_no_response_log_candidate_id", "candidate_no_response_log", ["candidate_id"])
    op.create_index("ix_candidate_no_response_log_conversation_id", "candidate_no_response_log", ["conversation_id"])


def downgrade():
    op.drop_index("ix_candidate_no_response_log_conversation_id", table_name="candidate_no_response_log")
    op.drop_index("ix_candidate_no_response_log_candidate_id", table_name="candidate_no_response_log")
    op.drop_index("ix_candidate_no_response_log_tenant_id", table_name="candidate_no_response_log")
    op.drop_table("candidate_no_response_log")

    op.drop_index("ix_follow_up_schedule_job_queue", table_name="follow_up_schedule")
    op.drop_index("ix_follow_up_schedule_conversation_id", table_name="follow_up_schedule")
    op.drop_index("ix_follow_up_schedule_candidate_id", table_name="follow_up_schedule")
    op.drop_index("ix_follow_up_schedule_tenant_id", table_name="follow_up_schedule")
    op.drop_table("follow_up_schedule")
