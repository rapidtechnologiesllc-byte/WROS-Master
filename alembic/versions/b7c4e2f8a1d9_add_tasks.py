"""add tasks / task_reassignment_requests / task_capacity_alerts (S-434)

Revision ID: b7c4e2f8a1d9
Revises: a9c4e7f1d3b5
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c4e2f8a1d9"
down_revision = "a9c4e7f1d3b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(30), nullable=False, server_default="GENERAL"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False, server_default="MEDIUM"),
        sa.Column("priority_challenged", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("priority_challenge_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(15), nullable=False, server_default="NEW"),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_user_id", sa.String(50), nullable=True),
        sa.Column("created_by_user_id", sa.String(50), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("is_external", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("visibility_scope", sa.String(35), nullable=False, server_default="ASSIGNEE_MANAGER_DEPARTMENT"),
        sa.Column("is_escalated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tasks_tenant_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_tasks_department_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.UserID"], name="fk_tasks_assigned_to_user_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.UserID"], name="fk_tasks_created_by_user_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], name="fk_tasks_parent_task_id", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "priority NOT IN ('URGENT') OR priority_challenge_note IS NOT NULL OR priority_challenged = 0",
            name="ck_task_urgent_has_validation_attempt",
        ),
    )
    op.create_index("ix_tasks_department_id", "tasks", ["department_id"])
    op.create_index("ix_tasks_assigned_to_user_id", "tasks", ["assigned_to_user_id"])
    op.create_index("ix_tasks_created_by_user_id", "tasks", ["created_by_user_id"])
    op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])

    op.create_table(
        "task_reassignment_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.String(50), nullable=False),
        sa.Column("suggested_to_user_id", sa.String(50), nullable=True),
        sa.Column("reason", sa.String(200), nullable=False, server_default="ASSIGNEE_UNAVAILABLE"),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("approved_by_user_id", sa.String(50), nullable=True),
        sa.Column("final_to_user_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_task_reassign_task_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.UserID"], name="fk_task_reassign_from_user_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["suggested_to_user_id"], ["users.UserID"], name="fk_task_reassign_suggested_to_user_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.UserID"], name="fk_task_reassign_approved_by_user_id", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["final_to_user_id"], ["users.UserID"], name="fk_task_reassign_final_to_user_id", ondelete="NO ACTION"),
    )
    op.create_index("ix_task_reassignment_requests_task_id", "task_reassignment_requests", ["task_id"])

    op.create_table(
        "task_capacity_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("open_task_count", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.UserID"], name="fk_task_capacity_alert_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_task_capacity_alert_department_id", ondelete="NO ACTION"),
    )
    op.create_index("ix_task_capacity_alerts_user_id", "task_capacity_alerts", ["user_id"])


def downgrade():
    op.drop_index("ix_task_capacity_alerts_user_id", table_name="task_capacity_alerts")
    op.drop_table("task_capacity_alerts")
    op.drop_index("ix_task_reassignment_requests_task_id", table_name="task_reassignment_requests")
    op.drop_table("task_reassignment_requests")
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
    op.drop_index("ix_tasks_created_by_user_id", table_name="tasks")
    op.drop_index("ix_tasks_assigned_to_user_id", table_name="tasks")
    op.drop_index("ix_tasks_department_id", table_name="tasks")
    op.drop_table("tasks")
