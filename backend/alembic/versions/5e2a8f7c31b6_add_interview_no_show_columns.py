import logging
"""S-052/HRMS-0452: add no-show tracking columns to submission_interviews

Revision ID: 5e2a8f7c31b6
Revises: 3a7c5e91d0f4
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "5e2a8f7c31b6"
down_revision = "3a7c5e91d0f4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.add_column(sa.Column("no_show_check_in_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("no_show_confirmed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("no_show_reschedule_offer_sent_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("no_show_no_response_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("submission_interviews") as batch_op:
        batch_op.drop_column("no_show_no_response_at")
        batch_op.drop_column("no_show_reschedule_offer_sent_at")
        batch_op.drop_column("no_show_confirmed_at")
        batch_op.drop_column("no_show_check_in_at")
