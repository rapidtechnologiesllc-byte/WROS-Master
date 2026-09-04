import logging
"""add candidate_opportunity_watches (ready-for-opportunity workflow)

Revision ID: d4e9a1c6f3b8
Revises: c8d5f3a9b2e7
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e9a1c6f3b8"
down_revision = "c8d5f3a9b2e7"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_opportunity_watches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("matched_job_id", sa.String(50), nullable=True),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        sa.Column("nudged_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_cow_tenant_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidateID"], name="fk_cow_candidate_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_job_id"], ["jobs.jobID"], name="fk_cow_matched_job_id", ondelete="NO ACTION"),
    )
    op.create_index("ix_cow_candidate_id", "candidate_opportunity_watches", ["candidate_id"])
    op.create_index("ix_cow_is_active", "candidate_opportunity_watches", ["is_active"])
    op.create_index("ix_cow_tenant_id", "candidate_opportunity_watches", ["tenant_id"])

def downgrade():
    op.drop_index("ix_cow_tenant_id", table_name="candidate_opportunity_watches")
    op.drop_index("ix_cow_is_active", table_name="candidate_opportunity_watches")
    op.drop_index("ix_cow_candidate_id", table_name="candidate_opportunity_watches")
    op.drop_table("candidate_opportunity_watches")
