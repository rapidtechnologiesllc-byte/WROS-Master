import logging
"""Help Desk/IT-HR ticketing: widen tasks.task_type, add ticket_category_routes / ticket_sla_policies / ticket_details

Revision ID: c8d5f3a9b2e7
Revises: b7c4e2f8a1d9
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d5f3a9b2e7"
down_revision = "b7c4e2f8a1d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("task_type", type_="check")
        batch_op.create_check_constraint("task_type", "task_type IN ('GENERAL', 'TICKET')")

    op.create_table(
        "ticket_category_routes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_ticket_category_routes_department_id", ondelete="NO ACTION"),
        sa.UniqueConstraint("category", "subcategory", name="uq_ticket_category_route"),
    )

    op.create_table(
        "ticket_sla_policies",
        sa.Column("priority", sa.String(10), primary_key=True),
        sa.Column("response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.bulk_insert(
        sa.table(
            "ticket_sla_policies",
            sa.column("priority", sa.String),
            sa.column("response_minutes", sa.Integer),
            sa.column("resolution_minutes", sa.Integer),
        ),
        [
            {"priority": "URGENT", "response_minutes": 30, "resolution_minutes": 4 * 60},
            {"priority": "HIGH", "response_minutes": 2 * 60, "resolution_minutes": 8 * 60},
            {"priority": "MEDIUM", "response_minutes": 8 * 60, "resolution_minutes": 3 * 24 * 60},
            {"priority": "LOW", "response_minutes": 24 * 60, "resolution_minutes": 7 * 24 * 60},
        ],
    )

    op.create_table(
        "ticket_details",
        sa.Column("task_id", sa.Integer(), primary_key=True),
        sa.Column("impact", sa.String(30), nullable=False),
        sa.Column("urgency", sa.String(15), nullable=False),
        sa.Column("response_due_at", sa.DateTime(), nullable=False),
        sa.Column("resolution_due_at", sa.DateTime(), nullable=False),
        sa.Column("first_response_at", sa.DateTime(), nullable=True),
        sa.Column("response_breached", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("resolution_breached", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_ticket_details_task_id", ondelete="CASCADE"),
    )


def downgrade():
    op.drop_table("ticket_details")
    op.drop_table("ticket_sla_policies")
    op.drop_table("ticket_category_routes")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("task_type", type_="check")
        batch_op.create_check_constraint(
            "task_type",
            "task_type IN ('GENERAL', 'TICKET_HR', 'TICKET_IT', 'TICKET_FACILITIES', 'TICKET_OTHER')",
        )
