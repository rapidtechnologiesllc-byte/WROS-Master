import logging
"""S-028/HRMS-0428: add candidate_resume_parsed table

Revision ID: b23976adb15d
Revises: a6b7c8d9e0f1
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "b23976adb15d"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_resume_parsed",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False, unique=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(300), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("current_title", sa.String(200), nullable=True),
        sa.Column("current_employer", sa.String(200), nullable=True),
        sa.Column("work_history", sa.JSON(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("certifications", sa.JSON(), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("total_experience_months", sa.Integer(), nullable=True),
        sa.Column("total_experience_years", sa.Float(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("parser_version", sa.String(20), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_candidate_resume_parsed_tenant_id", "candidate_resume_parsed", ["tenant_id"])
    op.create_index("ix_candidate_resume_parsed_candidate_id", "candidate_resume_parsed", ["candidate_id"], unique=True)


def downgrade():
    op.drop_index("ix_candidate_resume_parsed_candidate_id", table_name="candidate_resume_parsed")
    op.drop_index("ix_candidate_resume_parsed_tenant_id", table_name="candidate_resume_parsed")
    op.drop_table("candidate_resume_parsed")
