"""S-024/HRMS-0424: add candidate_field_skips table

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_field_skips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("skipped_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_field_skips_tenant_id", "candidate_field_skips", ["tenant_id"])
    op.create_index("ix_candidate_field_skips_candidate_id", "candidate_field_skips", ["candidate_id"])


def downgrade():
    op.drop_index("ix_candidate_field_skips_candidate_id", table_name="candidate_field_skips")
    op.drop_index("ix_candidate_field_skips_tenant_id", table_name="candidate_field_skips")
    op.drop_table("candidate_field_skips")
