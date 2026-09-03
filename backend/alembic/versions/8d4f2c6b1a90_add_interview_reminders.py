import logging
"""S-050/HRMS-0450: add interview_reminders table

Revision ID: 8d4f2c6b1a90
Revises: 6b1e9d4a83f2
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "8d4f2c6b1a90"
down_revision = "6b1e9d4a83f2"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "interview_reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("interview_id", sa.String(36), sa.ForeignKey("submission_interviews.id"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("reminder_type", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_interview_reminders_tenant_id", "interview_reminders", ["tenant_id"])
    op.create_index("ix_interview_reminders_interview_id", "interview_reminders", ["interview_id"])
    op.create_index("ix_interview_reminders_candidate_id", "interview_reminders", ["candidate_id"])
    op.create_index("ix_interview_reminders_job_queue", "interview_reminders", ["status", "scheduled_at"])

def downgrade():
    op.drop_index("ix_interview_reminders_job_queue", table_name="interview_reminders")
    op.drop_index("ix_interview_reminders_candidate_id", table_name="interview_reminders")
    op.drop_index("ix_interview_reminders_interview_id", table_name="interview_reminders")
    op.drop_index("ix_interview_reminders_tenant_id", table_name="interview_reminders")
    op.drop_table("interview_reminders")
