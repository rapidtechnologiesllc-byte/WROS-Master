import logging
"""add error_log table (S-215/HRMS-0117)

Revision ID: f6a3c9e1b7d2
Revises: e2f7b4d1a9c3
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a3c9e1b7d2"
down_revision = "e2f7b4d1a9c3"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "error_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("request_context", sa.Text(), nullable=True),
        sa.Column("integration_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_error_log_tenant_id", ondelete="NO ACTION"),
    )
    op.create_index("ix_error_log_tenant_id", "error_log", ["tenant_id"])
    op.create_index("ix_error_log_error_type", "error_log", ["error_type"])
    op.create_index("ix_error_log_severity", "error_log", ["severity"])
    op.create_index("ix_error_log_integration_name", "error_log", ["integration_name"])
    op.create_index("ix_error_log_created_at", "error_log", ["created_at"])

def downgrade():
    op.drop_index("ix_error_log_created_at", table_name="error_log")
    op.drop_index("ix_error_log_integration_name", table_name="error_log")
    op.drop_index("ix_error_log_severity", table_name="error_log")
    op.drop_index("ix_error_log_error_type", table_name="error_log")
    op.drop_index("ix_error_log_tenant_id", table_name="error_log")
    op.drop_table("error_log")
