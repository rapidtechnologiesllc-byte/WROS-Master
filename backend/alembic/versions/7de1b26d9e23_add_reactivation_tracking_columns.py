import logging
"""S-045/HRMS-0445: add reactivation tracking columns to candidate_ghosting_status

Revision ID: 7de1b26d9e23
Revises: 547d41705e1d
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "7de1b26d9e23"
down_revision = "547d41705e1d"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("candidate_ghosting_status") as batch_op:
        batch_op.add_column(sa.Column("reactivation_attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_reactivation_sent_at", sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table("candidate_ghosting_status") as batch_op:
        batch_op.drop_column("last_reactivation_sent_at")
        batch_op.drop_column("reactivation_attempt_count")
