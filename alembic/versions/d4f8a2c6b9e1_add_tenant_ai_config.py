"""add tenant_ai_config tables (S-077/HRMS-0477)

Revision ID: d4f8a2c6b9e1
Revises: b2c6e8a4d7f3
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f8a2c6b9e1"
down_revision = "b2c6e8a4d7f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenant_ai_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), nullable=False, unique=True),
        sa.Column("greeting_channel", sa.String(20), nullable=False, server_default="BOTH_PARALLEL"),
        sa.Column("whatsapp_followup_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("email_followup_hours", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("max_followup_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("ghosting_reactivation_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("digest_send_time", sa.String(5), nullable=False, server_default="08:00"),
        sa.Column("sla_first_contact_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("sla_no_contact_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("qualification_field_order", sa.JSON(), nullable=True),
        sa.Column("escalation_keywords", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.UserID"], name="fk_tenant_ai_config_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.UserID"], name="fk_tenant_ai_config_updated_by", ondelete="NO ACTION"),
    )
    op.create_index("ix_tenant_ai_config_tenant_id", "tenant_ai_config", ["tenant_id"])

    op.create_table(
        "tenant_ai_config_change_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.UserID"], name="fk_tenant_ai_config_change_log_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.UserID"], name="fk_tenant_ai_config_change_log_updated_by", ondelete="NO ACTION"),
    )
    op.create_index("ix_tenant_ai_config_change_log_tenant_id", "tenant_ai_config_change_log", ["tenant_id"])


def downgrade():
    op.drop_index("ix_tenant_ai_config_change_log_tenant_id", table_name="tenant_ai_config_change_log")
    op.drop_table("tenant_ai_config_change_log")
    op.drop_index("ix_tenant_ai_config_tenant_id", table_name="tenant_ai_config")
    op.drop_table("tenant_ai_config")
