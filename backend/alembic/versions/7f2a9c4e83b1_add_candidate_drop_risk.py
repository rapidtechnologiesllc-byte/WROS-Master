import logging
"""S-060/HRMS-0460: add candidate_drop_risk table

Revision ID: 7f2a9c4e83b1
Revises: 1d5f8b3a70c4
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "7f2a9c4e83b1"
down_revision = "1d5f8b3a70c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_drop_risk",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("drop_risk_score", sa.Integer(), nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="candidate_drop_risk_level", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("risk_signals", sa.JSON(), nullable=True),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_drop_risk"),
    )
    op.create_index("ix_candidate_drop_risk_tenant_id", "candidate_drop_risk", ["tenant_id"])
    op.create_index("ix_candidate_drop_risk_candidate_id", "candidate_drop_risk", ["candidate_id"])


def downgrade():
    op.drop_index("ix_candidate_drop_risk_candidate_id", table_name="candidate_drop_risk")
    op.drop_index("ix_candidate_drop_risk_tenant_id", table_name="candidate_drop_risk")
    op.drop_table("candidate_drop_risk")
