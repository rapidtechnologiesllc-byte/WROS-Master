import logging
"""S-054/HRMS-0454: add offer_faq_active column to candidate_conversations

Revision ID: 7f3d9a2c48e1
Revises: 5e2a8f7c31b6
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "7f3d9a2c48e1"
down_revision = "5e2a8f7c31b6"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("candidate_conversations") as batch_op:
        batch_op.add_column(sa.Column("offer_faq_active", sa.Boolean(), nullable=False, server_default="0"))

def downgrade():
    with op.batch_alter_table("candidate_conversations") as batch_op:
        batch_op.drop_column("offer_faq_active")
