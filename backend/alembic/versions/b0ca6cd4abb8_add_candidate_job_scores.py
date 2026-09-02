import logging
"""S-037/HRMS-0437: add candidate_job_scores table + structured job requirement columns

Revision ID: b0ca6cd4abb8
Revises: 0040e68b0bea
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "b0ca6cd4abb8"
down_revision = "0040e68b0bea"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_job_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("job_id", sa.String(50), sa.ForeignKey("jobs.jobID"), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=True),
        sa.Column("compensation_score", sa.Integer(), nullable=True),
        sa.Column("availability_score", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "candidate_id", "job_id", name="uq_candidate_job_score"),
    )
    op.create_index("ix_candidate_job_scores_tenant_id", "candidate_job_scores", ["tenant_id"])
    op.create_index("ix_candidate_job_scores_candidate_id", "candidate_job_scores", ["candidate_id"])
    op.create_index("ix_candidate_job_scores_job_id", "candidate_job_scores", ["job_id"])

    op.add_column("jobs", sa.Column("required_skills_canonical", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("min_experience_years", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("domain", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("certifications_preferred", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("jobs", "certifications_preferred")
    op.drop_column("jobs", "domain")
    op.drop_column("jobs", "min_experience_years")
    op.drop_column("jobs", "required_skills_canonical")

    op.drop_index("ix_candidate_job_scores_job_id", table_name="candidate_job_scores")
    op.drop_index("ix_candidate_job_scores_candidate_id", table_name="candidate_job_scores")
    op.drop_index("ix_candidate_job_scores_tenant_id", table_name="candidate_job_scores")
    op.drop_table("candidate_job_scores")
