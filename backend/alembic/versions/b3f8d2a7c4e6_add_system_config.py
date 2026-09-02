import logging
"""add system_config table (S-213/HRMS-0115)

Revision ID: b3f8d2a7c4e6
Revises: a8e4d2c6f9b1
Create Date: 2026-08-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b3f8d2a7c4e6"
down_revision = "a8e4d2c6f9b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("business_unit_id", sa.Integer(), nullable=True),
        sa.Column("config_category", sa.String(20), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_system_config_tenant_id"),
        sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"], name="fk_system_config_business_unit_id"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.UserID"], name="fk_system_config_updated_by"),
        sa.UniqueConstraint("tenant_id", "business_unit_id", "config_key", name="uq_system_config_scope_key"),
    )
    op.create_index("ix_system_config_tenant_id", "system_config", ["tenant_id"])
    op.create_index("ix_system_config_business_unit_id", "system_config", ["business_unit_id"])


def downgrade():
    op.drop_index("ix_system_config_business_unit_id", table_name="system_config")
    op.drop_index("ix_system_config_tenant_id", table_name="system_config")
    op.drop_table("system_config")
