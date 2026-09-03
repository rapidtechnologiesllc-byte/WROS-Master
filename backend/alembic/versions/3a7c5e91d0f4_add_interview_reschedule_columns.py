import logging
"""S-051/HRMS-0451: add interview reschedule columns, replace one-per-submission-level unique constraint with a partial index

Revision ID: 3a7c5e91d0f4
Revises: 8d4f2c6b1a90
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "3a7c5e91d0f4"
down_revision = "8d4f2c6b1a90"
branch_labels = None
depends_on = None

def upgrade():
    # A self-referential FK added inline via add_column() during SQLite
    # batch recreate hits a real alembic/SQLAlchemy bug ("Constraint
    # must have a name") -- add the column plain, then attach the named
    # FK constraint separately (verified against both orderings).
    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.add_column(sa.Column("reschedule_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("rescheduled_from_interview_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("superseded_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key("fk_rescheduled_from_interview", "submission_interviews", ["rescheduled_from_interview_id"], ["id"])
        batch_op.drop_constraint("uq_one_interview_per_level_per_submission", type_="unique")

    op.create_index(
        "ix_one_current_interview_per_level", "submission_interviews", ["submission_id", "level"],
        unique=True, sqlite_where=sa.text("superseded_at IS NULL"), mssql_where=sa.text("superseded_at IS NULL"),
    )

def downgrade():
    op.drop_index("ix_one_current_interview_per_level", table_name="submission_interviews")

    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.create_unique_constraint("uq_one_interview_per_level_per_submission", ["submission_id", "level"])
        batch_op.drop_constraint("fk_rescheduled_from_interview", type_="foreignkey")
        batch_op.drop_column("superseded_at")
        batch_op.drop_column("rescheduled_from_interview_id")
        batch_op.drop_column("reschedule_count")
