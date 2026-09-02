import logging
"""add preboarding_touchpoints table (S-067/HRMS-0467)

Revision ID: a9c4e7f1d3b5
Revises: f3b6d9e2c8a4
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a9c4e7f1d3b5"
down_revision = "f3b6d9e2c8a4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "preboarding_touchpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("candidate_id", sa.String(50), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("touchpoint_type", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.UserID"], name="fk_preboarding_touchpoints_tenant_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidateID"], name="fk_preboarding_touchpoints_candidate_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offer_id"], ["offer_letters.id"], name="fk_preboarding_touchpoints_offer_id", ondelete="CASCADE"),
    )
    op.create_index("ix_preboarding_touchpoints_tenant_id", "preboarding_touchpoints", ["tenant_id"])
    op.create_index("ix_preboarding_touchpoints_candidate_id", "preboarding_touchpoints", ["candidate_id"])
    op.create_index("ix_preboarding_touchpoints_offer_id", "preboarding_touchpoints", ["offer_id"])


def downgrade():
    op.drop_index("ix_preboarding_touchpoints_offer_id", table_name="preboarding_touchpoints")
    op.drop_index("ix_preboarding_touchpoints_candidate_id", table_name="preboarding_touchpoints")
    op.drop_index("ix_preboarding_touchpoints_tenant_id", table_name="preboarding_touchpoints")
    op.drop_table("preboarding_touchpoints")
