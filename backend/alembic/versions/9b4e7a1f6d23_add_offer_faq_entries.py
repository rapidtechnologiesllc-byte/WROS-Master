import logging
"""S-055/HRMS-0455: add offer_faq_entries table

Revision ID: 9b4e7a1f6d23
Revises: 7f3d9a2c48e1
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "9b4e7a1f6d23"
down_revision = "7f3d9a2c48e1"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "offer_faq_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "topic", name="uq_offer_faq_entry"),
    )
    op.create_index("ix_offer_faq_entries_tenant_id", "offer_faq_entries", ["tenant_id"])

def downgrade():
    op.drop_index("ix_offer_faq_entries_tenant_id", table_name="offer_faq_entries")
    op.drop_table("offer_faq_entries")
