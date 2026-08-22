"""add event_log table (S-078/HRMS-0478)

Revision ID: e7a1c3f9b2d6
Revises: f8a9b0c1d2e3
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e7a1c3f9b2d6"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("candidate_id", sa.String(50), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_version", sa.String(10), nullable=False, server_default="v1"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("emitted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.UserID"], name="fk_event_log_tenant_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidateID"], name="fk_event_log_candidate_id", ondelete="CASCADE"),
    )
    op.create_index("ix_event_log_tenant_id", "event_log", ["tenant_id"])
    op.create_index("ix_event_log_candidate_id", "event_log", ["candidate_id"])
    op.create_index("ix_event_log_event_type", "event_log", ["event_type"])
    op.create_index("ix_event_log_emitted_at", "event_log", ["emitted_at"])


def downgrade():
    op.drop_index("ix_event_log_emitted_at", table_name="event_log")
    op.drop_index("ix_event_log_event_type", table_name="event_log")
    op.drop_index("ix_event_log_candidate_id", table_name="event_log")
    op.drop_index("ix_event_log_tenant_id", table_name="event_log")
    op.drop_table("event_log")
