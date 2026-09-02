import logging
"""S-030/HRMS-0430: add resume_completeness_score columns

Revision ID: 0eb7ca2cdb11
Revises: eb1544547b90
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0eb7ca2cdb11"
down_revision = "eb1544547b90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_resume_parsed", sa.Column("resume_completeness_score", sa.Integer(), nullable=True))
    op.add_column("candidate_resume_parsed", sa.Column("score_calculated_at", sa.DateTime(), nullable=True))
    op.add_column("candidates", sa.Column("resume_completeness_score", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("candidates", "resume_completeness_score")
    op.drop_column("candidate_resume_parsed", "score_calculated_at")
    op.drop_column("candidate_resume_parsed", "resume_completeness_score")
