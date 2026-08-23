"""add Executive Signal & Culture Agent tables (feedback cycle, recognition drafts, concern intake)

Revision ID: e2f7b4d1a9c3
Revises: d4e9a1c6f3b8
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f7b4d1a9c3"
down_revision = "d4e9a1c6f3b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_feedback_cycles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("quarter_label", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="OPEN"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_efc_tenant_id", ondelete="NO ACTION"),
    )

    op.create_table(
        "employee_feedback_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cycle_id", sa.String(36), nullable=False),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cycle_id"], ["employee_feedback_cycles.id"], name="fk_efr_cycle_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name="fk_efr_employee_id", ondelete="CASCADE"),
    )
    op.create_index("ix_efr_cycle_id", "employee_feedback_responses", ["cycle_id"])
    op.create_index("ix_efr_employee_id", "employee_feedback_responses", ["employee_id"])

    op.create_table(
        "recognition_message_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("occasion", sa.String(30), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("approved_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name="fk_rmd_employee_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.UserID"], name="fk_rmd_approved_by", ondelete="NO ACTION"),
    )
    op.create_index("ix_rmd_employee_id", "recognition_message_drafts", ["employee_id"])

    op.create_table(
        "employee_concern_intakes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(36), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(15), nullable=True),
        sa.Column("resolution_text", sa.Text(), nullable=True),
        sa.Column("created_task_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name="fk_eci_employee_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_task_id"], ["tasks.id"], name="fk_eci_created_task_id", ondelete="NO ACTION"),
    )
    op.create_index("ix_eci_employee_id", "employee_concern_intakes", ["employee_id"])


def downgrade():
    op.drop_index("ix_eci_employee_id", table_name="employee_concern_intakes")
    op.drop_table("employee_concern_intakes")
    op.drop_index("ix_rmd_employee_id", table_name="recognition_message_drafts")
    op.drop_table("recognition_message_drafts")
    op.drop_index("ix_efr_employee_id", table_name="employee_feedback_responses")
    op.drop_index("ix_efr_cycle_id", table_name="employee_feedback_responses")
    op.drop_table("employee_feedback_responses")
    op.drop_table("employee_feedback_cycles")
