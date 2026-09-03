import logging
"""S-029/HRMS-0429: add candidate_skill_tags table

Revision ID: eb1544547b90
Revises: b23976adb15d
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "eb1544547b90"
down_revision = "b23976adb15d"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_skill_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("skill_canonical", sa.String(100), nullable=False),
        sa.Column("skill_raw", sa.String(200), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="RESUME"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "candidate_id", "skill_canonical", name="uq_candidate_skill_tag"),
    )
    op.create_index("ix_candidate_skill_tags_tenant_id", "candidate_skill_tags", ["tenant_id"])
    op.create_index("ix_candidate_skill_tags_candidate_id", "candidate_skill_tags", ["candidate_id"])
    op.create_index("ix_candidate_skill_tags_lookup", "candidate_skill_tags", ["tenant_id", "candidate_id", "skill_canonical"])

def downgrade():
    op.drop_index("ix_candidate_skill_tags_lookup", table_name="candidate_skill_tags")
    op.drop_index("ix_candidate_skill_tags_candidate_id", table_name="candidate_skill_tags")
    op.drop_index("ix_candidate_skill_tags_tenant_id", table_name="candidate_skill_tags")
    op.drop_table("candidate_skill_tags")
