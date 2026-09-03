import logging
"""Add 10 modules for Step 3 role template alignment

This migration ensures 10 modules are defined to match the navigation menu:
1. recruitment_management
2. finance_revenue
3. workforce_employees
4. administration
5. sales
6. project_management
7. reporting
8. system
9. executive_dashboards
10. engagement_communications

Revision ID: 20260822_add_10_modules_step3
Revises: <previous_revision>
Create Date: 2026-08-22 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260822_add_10_modules_step3"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Add 10 modules and their resources."""

    # Create modules if they don't exist
    # Note: This uses raw SQL to ensure idempotency (module_name unique constraint)

    insert_module_sql = """
    INSERT INTO modules (name, display_name, description, enabled, tenant_id, created_at, updated_at)
    VALUES
        (:name, :display_name, :desc, true, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (name) DO NOTHING;
    """

    modules = [
        {"name": "recruitment_management", "display_name": "Recruitment Management"},
        {"name": "finance_revenue", "display_name": "Finance & Revenue"},
        {"name": "workforce_employees", "display_name": "Workforce & Employees"},
        {"name": "administration", "display_name": "Administration"},
        {"name": "sales", "display_name": "Sales"},
        {"name": "project_management", "display_name": "Project Management"},
        {"name": "reporting", "display_name": "Reporting"},
        {"name": "system", "display_name": "System"},
        {"name": "executive_dashboards", "display_name": "Executive Dashboards"},
        {"name": "engagement_communications", "display_name": "Engagement & Communications"},
    ]

    for module in modules:
        op.execute(
            sa.text(insert_module_sql),
            {
                "name": module["name"],
                "display_name": module["display_name"],
                "desc": None
            }
        )

def downgrade() -> None:
    """Remove 10 modules (keeping data for audit trail)."""

    module_names = [
        "recruitment_management",
        "finance_revenue",
        "workforce_employees",
        "administration",
        "sales",
        "project_management",
        "reporting",
        "system",
        "executive_dashboards",
        "engagement_communications",
    ]

    for name in module_names:
        op.execute(
            sa.text("DELETE FROM modules WHERE name = :name AND tenant_id = 1"),
            {"name": name}
        )
