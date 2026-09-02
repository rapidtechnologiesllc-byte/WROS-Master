import logging
"""S-039/HRMS-0439: add jobs.urgency

Revision ID: 4d8cb154d0b8
Revises: bfaccf034fff
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "4d8cb154d0b8"
down_revision = "bfaccf034fff"
branch_labels = None
depends_on = None

_URGENCY_VALUES = "'IMMEDIATE', 'HIGH', 'NORMAL', 'FLEXIBLE'"


def upgrade():
    # batch mode -- portable across the real MSSQL target and the SQLite
    # throwaway DB this migration is verified against in isolation before
    # ever touching the real database (SQLite has no ALTER-constraint
    # support outside batch mode; MSSQL runs these as plain ALTER
    # statements either way).
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("urgency", sa.String(20), nullable=True))
        batch_op.create_check_constraint("ck_jobs_urgency", f"urgency IN ({_URGENCY_VALUES}) OR urgency IS NULL")


def downgrade():
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("ck_jobs_urgency", type_="check")
        batch_op.drop_column("urgency")
