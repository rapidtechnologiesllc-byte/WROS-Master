import logging
"""add thunder pause controls (S-075/HRMS-0475)

Revision ID: b2c6e8a4d7f3
Revises: 9c3e5f7a1b4d
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c6e8a4d7f3"
down_revision = "9c3e5f7a1b4d"
branch_labels = None
depends_on = None


def upgrade():
    # Named FK attached via batch mode -- same convention
    # 3a7c5e91d0f4 established (an inline FK on add_column() during a
    # SQLite batch recreate hits a real alembic bug; add plain, then
    # attach the named constraint separately).
    with op.batch_alter_table("candidate_conversations") as batch_op:
        batch_op.add_column(sa.Column("is_thunder_paused", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("thunder_paused_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("thunder_resume_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("thunder_paused_by", sa.String(50), nullable=True))
        batch_op.create_foreign_key(
            "fk_candidate_conversations_thunder_paused_by", "users",
            ["thunder_paused_by"], ["UserID"],
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("thunder_enabled", sa.Boolean(), nullable=False, server_default="1"))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("thunder_enabled")

    with op.batch_alter_table("candidate_conversations") as batch_op:
        batch_op.drop_constraint("fk_candidate_conversations_thunder_paused_by", type_="foreignkey")
        batch_op.drop_column("thunder_paused_by")
        batch_op.drop_column("thunder_resume_at")
        batch_op.drop_column("thunder_paused_at")
        batch_op.drop_column("is_thunder_paused")
