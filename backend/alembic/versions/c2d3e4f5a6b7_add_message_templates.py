import logging
"""S-014/HRMS-0414: add message_templates table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(50), nullable=True),
        sa.Column("approved_by", sa.String(50), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "template_key", "version", "channel", name="uq_message_template_version"),
    )
    op.create_index("ix_message_templates_tenant_id", "message_templates", ["tenant_id"])
    op.create_index("ix_message_templates_template_key", "message_templates", ["template_key"])


def downgrade():
    op.drop_index("ix_message_templates_template_key", table_name="message_templates")
    op.drop_index("ix_message_templates_tenant_id", table_name="message_templates")
    op.drop_table("message_templates")
