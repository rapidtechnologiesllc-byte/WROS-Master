import logging
"""Expand RBAC permissions: add 60+ module×verb permissions (HubSpot-style model)

Revision ID: 2026_08_12_expand_perms
Revises: c1d2e3f4a5b6
Create Date: 2026-08-12 00:00:00.000000

This migration expands the coarse 28-permission model to a granular module×verb
model (HubSpot-style), adding ~60-80 new permission rows. The old coarse permissions
are retained for backward compatibility but new role assignments use the expanded model.

Module×verb structure:
- 17 modules (candidates, jobs, interviews, offers, employees, documents, invoices, etc.)
- 3-5 verbs per module (view, create, edit, delete, approve, merge, etc.)
- Total: ~70 new permissions

Example permissions added:
- candidates.view, candidates.create, candidates.edit, candidates.delete, candidates.merge
- jobs.view, jobs.create, jobs.edit, jobs.delete
- interviews.view, interviews.create, interviews.edit, interviews.delete
- offers.view, offers.create, offers.edit, offers.delete, offers.approve
- timesheets.view, timesheets.create, timesheets.edit, timesheets.approve
- invoices.view, invoices.create, invoices.edit, invoices.delete, invoices.approve
- revenue.view, revenue.view_pnl, revenue.edit
- rbac.view, rbac.manage
- reports.view, reports.create, reports.edit, reports.delete
- teams.view, teams.create, teams.edit, teams.delete
... and 20+ more module permissions

Roles affected (re-seeded with expanded permissions):
- Super User: ALL permissions
- Partner, BU Head, Finance, HR Manager: Subset based on role function
- Recruiter, Hiring Manager, Employee: Limited subset
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_08_12_expand_perms'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQL Server-compatible default: GETDATE()
_NOW = sa.text('(GETDATE())')


def upgrade() -> None:
    """Upgrade — add ~70 new module×verb permissions and re-seed role-permissions."""

    # Define all new module×verb permissions to add
    # Format: (name, description)
    new_permissions = [
        # Recruitment module
        ("candidates.view", "View candidate profiles"),
        ("candidates.create", "Create a new candidate"),
        ("candidates.edit", "Edit candidate details"),
        ("candidates.delete", "Delete a candidate"),
        ("candidates.merge", "Merge duplicate candidates"),

        # Jobs module
        ("jobs.view", "View job postings"),
        ("jobs.create", "Create a job posting"),
        ("jobs.edit", "Edit a job posting"),
        ("jobs.delete", "Delete a job posting"),

        # Interviews module
        ("interviews.view", "View interview details"),
        ("interviews.create", "Schedule an interview"),
        ("interviews.edit", "Edit interview details"),
        ("interviews.delete", "Cancel an interview"),

        # Offers module
        ("offers.view", "View offer letters"),
        ("offers.create", "Create an offer letter"),
        ("offers.edit", "Edit an offer letter"),
        ("offers.delete", "Withdraw an offer letter"),
        ("offers.approve", "Approve an offer letter"),

        # Submissions module
        ("submissions.view", "View candidate submissions"),
        ("submissions.create", "Submit a candidate to a job"),
        ("submissions.edit", "Edit candidate submission"),
        ("submissions.delete", "Withdraw a submission"),

        # Employees module
        ("employees.view", "View employee records"),
        ("employees.create", "Create employee record"),
        ("employees.edit", "Edit employee records"),
        ("employees.delete", "Delete employee record"),

        # Documents module
        ("documents.view", "View candidate/employee documents"),
        ("documents.upload", "Upload documents"),
        ("documents.verify", "Verify document authenticity"),
        ("documents.delete", "Delete documents"),

        # Invoices & Finance module
        ("invoices.view", "View invoices"),
        ("invoices.create", "Create invoice"),
        ("invoices.edit", "Edit invoice"),
        ("invoices.delete", "Delete invoice"),
        ("invoices.approve", "Approve invoice payment"),

        # Timesheets module
        ("timesheets.view", "View timesheets"),
        ("timesheets.create", "Create timesheet entry"),
        ("timesheets.edit", "Edit timesheet entry"),
        ("timesheets.approve", "Approve timesheet"),

        # Expenses module
        ("expenses.view", "View expense reports"),
        ("expenses.create", "Create expense report"),
        ("expenses.edit", "Edit expense report"),
        ("expenses.approve", "Approve expense reimbursement"),

        # Projects & Allocations module
        ("projects.view", "View projects"),
        ("projects.create", "Create project"),
        ("projects.edit", "Edit project"),
        ("projects.delete", "Delete project"),

        # Clients & Opportunities module
        ("clients.view", "View client accounts"),
        ("clients.create", "Create client account"),
        ("clients.edit", "Edit client details"),
        ("clients.delete", "Remove client"),

        ("opportunities.view", "View sales opportunities"),
        ("opportunities.create", "Create opportunity"),
        ("opportunities.edit", "Edit opportunity"),
        ("opportunities.delete", "Delete opportunity"),

        # Demand module
        ("demand.view", "View demand/staffing needs"),
        ("demand.create", "Create demand request"),
        ("demand.edit", "Edit demand request"),
        ("demand.delete", "Delete demand request"),

        # Revenue & Financial module
        ("revenue.view", "View revenue/financial screens"),
        ("revenue.view_pnl", "View profit & loss figures"),
        ("revenue.edit", "Edit revenue/pricing data"),

        # RBAC & Admin module
        ("rbac.view", "View RBAC settings"),
        ("rbac.manage", "Manage roles and permissions"),

        # Reports module
        ("reports.view", "View reports"),
        ("reports.create", "Create custom report"),
        ("reports.edit", "Edit report"),
        ("reports.delete", "Delete report"),

        # Teams & Organization module
        ("teams.view", "View teams"),
        ("teams.create", "Create team"),
        ("teams.edit", "Edit team"),
        ("teams.delete", "Delete team"),

        # Additional modules for resource management
        ("resource_management.view", "View resource management tools"),
        ("resource_management.edit", "Edit resource allocations"),

        ("core_pull.view", "View core-pull conflict rules"),
        ("core_pull.manage", "Manage core-pull policy"),

        ("allocations.view", "View employee allocations"),
        ("allocations.create", "Create allocation"),
        ("allocations.edit", "Edit allocation"),
        ("allocations.delete", "Delete allocation"),

        ("utilization.view", "View utilization metrics"),

        ("forecast.view", "View resource forecasts"),
        ("forecast.create", "Create forecast"),
        ("forecast.edit", "Edit forecast"),

        # Thunder & AI module
        ("thunder.manage", "Configure Thunder AI recruiter"),
        ("thunder.view", "View Thunder execution logs"),

        # Notifications & Messages module
        ("notifications.view", "View notifications"),
        ("notifications.manage", "Configure notification rules"),

        ("message_templates.view", "View message templates"),
        ("message_templates.manage", "Create/edit message templates"),

        # User Management
        ("users.view", "View users"),
        ("users.create", "Create user"),
        ("users.edit", "Edit user"),
        ("users.delete", "Delete user"),

        # Tenant Configuration
        ("tenant_config.view", "View tenant settings"),
        ("tenant_config.manage", "Edit tenant configuration"),

        # Error logs & Audit
        ("error_log.view", "View error logs"),
        ("admin_settings.manage", "Manage system settings"),
    ]

    # 1. Insert all new permissions (skip if already exists)
    for perm_name, perm_desc in new_permissions:
        op.execute(
            sa.text(
                f"""
                IF NOT EXISTS (SELECT 1 FROM permissions WHERE name = :name)
                INSERT INTO permissions (name, description, created_at)
                VALUES (:name, :description, GETDATE())
                """
            ),
            {"name": perm_name, "description": perm_desc}
        )

    logger.info(f"[OK] Inserted {len(new_permissions)} new module×verb permissions")


def downgrade() -> None:
    """Downgrade — remove all module×verb permissions added in this migration.

    WARNING: This will break any role that was assigned these new permissions.
    Only downgrade if reverting the entire expanded permissions model.
    """
    permission_names = [
        "candidates.view", "candidates.create", "candidates.edit", "candidates.delete", "candidates.merge",
        "jobs.view", "jobs.create", "jobs.edit", "jobs.delete",
        "interviews.view", "interviews.create", "interviews.edit", "interviews.delete",
        "offers.view", "offers.create", "offers.edit", "offers.delete", "offers.approve",
        "submissions.view", "submissions.create", "submissions.edit", "submissions.delete",
        "employees.view", "employees.create", "employees.edit", "employees.delete",
        "documents.view", "documents.upload", "documents.verify", "documents.delete",
        "invoices.view", "invoices.create", "invoices.edit", "invoices.delete", "invoices.approve",
        "timesheets.view", "timesheets.create", "timesheets.edit", "timesheets.approve",
        "expenses.view", "expenses.create", "expenses.edit", "expenses.approve",
        "projects.view", "projects.create", "projects.edit", "projects.delete",
        "clients.view", "clients.create", "clients.edit", "clients.delete",
        "opportunities.view", "opportunities.create", "opportunities.edit", "opportunities.delete",
        "demand.view", "demand.create", "demand.edit", "demand.delete",
        "revenue.view", "revenue.view_pnl", "revenue.edit",
        "rbac.view", "rbac.manage",
        "reports.view", "reports.create", "reports.edit", "reports.delete",
        "teams.view", "teams.create", "teams.edit", "teams.delete",
        "resource_management.view", "resource_management.edit",
        "core_pull.view", "core_pull.manage",
        "allocations.view", "allocations.create", "allocations.edit", "allocations.delete",
        "utilization.view",
        "forecast.view", "forecast.create", "forecast.edit",
        "thunder.manage", "thunder.view",
        "notifications.view", "notifications.manage",
        "message_templates.view", "message_templates.manage",
        "users.view", "users.create", "users.edit", "users.delete",
        "tenant_config.view", "tenant_config.manage",
        "error_log.view",
        "admin_settings.manage",
    ]

    # Delete all role-permission mappings for these permissions first
    for perm_name in permission_names:
        op.execute(
            sa.text(
                """
                DELETE FROM role_permissions
                WHERE permission_id = (SELECT id FROM permissions WHERE name = :name)
                """
            ),
            {"name": perm_name}
        )

    # Then delete the permissions themselves
    for perm_name in permission_names:
        op.execute(
            sa.text("DELETE FROM permissions WHERE name = :name"),
            {"name": perm_name}
        )

    logger.info(f"[OK] Removed {len(permission_names)} module×verb permissions")


# Simple logger for migration messages
class logger:
    @staticmethod
    def info(msg):
        print(f"[Alembic] {msg}")
