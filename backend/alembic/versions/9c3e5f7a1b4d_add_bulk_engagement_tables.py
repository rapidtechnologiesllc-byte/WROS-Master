import logging
"""S-074/HRMS-0474: add bulk_engagement_jobs + bulk_engagement_errors tables

Revision ID: 9c3e5f7a1b4d
Revises: 7a4d29b6c5e1
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9c3e5f7a1b4d"
down_revision = "7a4d29b6c5e1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "bulk_engagement_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("recruiter_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("candidate_ids", sa.JSON(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_bulk_engagement_jobs_tenant_id", "bulk_engagement_jobs", ["tenant_id"])
    op.create_index("ix_bulk_engagement_jobs_recruiter_id", "bulk_engagement_jobs", ["recruiter_id"])

    op.create_table(
        "bulk_engagement_errors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("bulk_engagement_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_bulk_engagement_errors_job_id", "bulk_engagement_errors", ["job_id"])

def downgrade():
    op.drop_index("ix_bulk_engagement_errors_job_id", table_name="bulk_engagement_errors")
    op.drop_table("bulk_engagement_errors")
    op.drop_index("ix_bulk_engagement_jobs_recruiter_id", table_name="bulk_engagement_jobs")
    op.drop_index("ix_bulk_engagement_jobs_tenant_id", table_name="bulk_engagement_jobs")
    op.drop_table("bulk_engagement_jobs")
