import logging
"""S-038/HRMS-0438: add candidate_job_flags table + job budget columns

Revision ID: bfaccf034fff
Revises: b0ca6cd4abb8
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "bfaccf034fff"
down_revision = "b0ca6cd4abb8"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_job_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("job_id", sa.String(50), sa.ForeignKey("jobs.jobID"), nullable=False),
        sa.Column("flag_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_job_flags_tenant_id", "candidate_job_flags", ["tenant_id"])
    op.create_index("ix_candidate_job_flags_candidate_id", "candidate_job_flags", ["candidate_id"])
    op.create_index("ix_candidate_job_flags_job_id", "candidate_job_flags", ["job_id"])
    op.create_index("ix_candidate_job_flags_lookup", "candidate_job_flags", ["tenant_id", "candidate_id", "job_id", "flag_type", "is_resolved"])

    op.add_column("jobs", sa.Column("budget_min", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("budget_max", sa.Integer(), nullable=True))

def downgrade():
    op.drop_column("jobs", "budget_max")
    op.drop_column("jobs", "budget_min")

    op.drop_index("ix_candidate_job_flags_lookup", table_name="candidate_job_flags")
    op.drop_index("ix_candidate_job_flags_job_id", table_name="candidate_job_flags")
    op.drop_index("ix_candidate_job_flags_candidate_id", table_name="candidate_job_flags")
    op.drop_index("ix_candidate_job_flags_tenant_id", table_name="candidate_job_flags")
    op.drop_table("candidate_job_flags")
