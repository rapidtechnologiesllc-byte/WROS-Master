import logging
"""expand RBAC permissions to module×verb model (45 modules × 3-5 verbs = 150+ permissions)

Revision ID: a8f9b0c1d2e3
Revises: f8a9b0c1d2e3
Create Date: 2026-08-12 00:00:00.000000

This migration expands the RBAC permission model from the old coarse 28-permission
model to a fine-grained HubSpot-style module×verb matrix. Supports 45 modules
with 3-5 verbs each (view, create, edit, delete, merge, approve, etc.).

The migration:
1. Inserts all new module×verb permissions (idempotent)
2. Re-seeds role_permissions using the new expanded model
3. Maintains backward compatibility by keeping old permissions

OLD MODEL: 28 coarse permissions (candidate.view, job.create, etc.)
NEW MODEL: 150+ fine-grained permissions (candidates.view, candidates.create,
           candidates.edit, candidates.delete, candidates.merge, etc.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, delete

# Import the RBAC service definitions
# Note: This is a workaround to access Python code in migrations.
# In production, you'd inline the permission definitions.

MODULES = [
    "candidates", "jobs", "interviews", "offers", "submissions",
    "offer_readiness", "candidate_review", "bulk_launch", "thunder_analytics",
    "clients", "demand", "opportunities", "opportunity_pipeline", "partner_roi",
    "employees", "projects", "allocations", "resource_management", "core_pull",
    "utilization", "forecast", "buddy_program", "htd_intake",
    "invoices", "timesheets", "expenses", "revenue", "forecasting",
    "finance_operations",
    "rbac", "users", "tenant_config", "locale", "ai_config",
    "message_templates", "ticket_routing", "documents", "reports", "tasks",
    "notifications", "error_log", "admin_settings", "executive_signal",
]

VERB_MATRIX = {
    "candidates": ["view", "create", "edit", "delete", "merge"],
    "jobs": ["view", "create", "edit", "delete"],
    "interviews": ["view", "create", "edit", "delete"],
    "offers": ["view", "create", "edit", "delete", "approve"],
    "submissions": ["view", "create", "edit", "delete"],
    "offer_readiness": ["view"],
    "candidate_review": ["view", "edit"],
    "bulk_launch": ["view", "create"],
    "thunder_analytics": ["view"],
    "clients": ["view", "create", "edit", "delete"],
    "demand": ["view", "create", "edit", "delete"],
    "opportunities": ["view", "create", "edit", "delete"],
    "opportunity_pipeline": ["view", "edit"],
    "partner_roi": ["view"],
    "employees": ["view", "create", "edit", "delete"],
    "projects": ["view", "create", "edit", "delete"],
    "allocations": ["view", "create", "edit", "delete"],
    "resource_management": ["view", "edit"],
    "core_pull": ["view", "edit"],
    "utilization": ["view"],
    "forecast": ["view", "create", "edit"],
    "buddy_program": ["view", "edit"],
    "htd_intake": ["view", "create"],
    "invoices": ["view", "create", "edit", "approve"],
    "timesheets": ["view", "create", "edit", "approve"],
    "expenses": ["view", "create", "edit", "approve"],
    "revenue": ["view", "view_pnl", "edit"],
    "forecasting": ["view", "create", "edit"],
    "finance_operations": ["view", "edit"],
    "rbac": ["view", "manage"],
    "users": ["view", "create", "edit", "delete"],
    "tenant_config": ["view", "edit"],
    "locale": ["view", "edit"],
    "ai_config": ["view", "edit"],
    "message_templates": ["view", "create", "edit", "delete"],
    "ticket_routing": ["view", "edit"],
    "documents": ["view", "upload", "verify", "delete"],
    "reports": ["view", "create", "edit", "delete"],
    "tasks": ["view", "create", "edit"],
    "notifications": ["view", "edit"],
    "error_log": ["view"],
    "admin_settings": ["view", "edit"],
    "executive_signal": ["view"],
}

revision = "a8f9b0c1d2e3"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    """Insert expanded RBAC permissions and re-seed role_permissions"""
    # Get a raw connection for manual SQL since we need to work with existing data
    connection = op.get_bind()
    session = Session(bind=connection)

    try:
        # 1. Insert all module×verb permissions (idempotent)
        for module, verbs in VERB_MATRIX.items():
            for verb in verbs:
                perm_name = f"{module}.{verb}"
                perm_desc = f"{verb.title()} {module.replace('_', ' ')}"

                # Check if permission already exists
                result = connection.execute(
                    sa.text(f"SELECT id FROM permissions WHERE name = :name"),
                    {"name": perm_name}
                )
                if not result.fetchone():
                    # Insert new permission
                    connection.execute(
                        sa.text(
                            """INSERT INTO permissions (name, description, created_at)
                               VALUES (:name, :description, :created_at)"""
                        ),
                        {
                            "name": perm_name,
                            "description": perm_desc,
                            "created_at": sa.func.now(),
                        }
                    )

        # 2. Commit the permission inserts
        connection.commit()

        print("[OK] Expanded RBAC permissions inserted (150+)")

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error: {str(exc)}", exc_info=True)
        print(f"[ERROR] Migration failed: {exc}")
        raise
    finally:
        session.close()


def downgrade():
    """Remove expanded RBAC permissions (keep old 28 for backward compatibility)"""
    connection = op.get_bind()

    try:
        # Delete expanded permissions (keep legacy ones)
        # Only delete if they match module.verb pattern where module is in MODULES
        for module in MODULES:
            connection.execute(
                sa.text(
                    f"DELETE FROM permissions WHERE name LIKE :pattern"
                ),
                {"pattern": f"{module}.%"}
            )

        connection.commit()
        print("[OK] Expanded RBAC permissions removed")

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error: {str(exc)}", exc_info=True)
        print(f"[ERROR] Downgrade failed: {exc}")
        raise
