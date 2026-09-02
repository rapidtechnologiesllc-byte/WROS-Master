"""
import logging
Initialize all Modules, Resources, and grant Super User role full permissions.

STRICT CONTRACT ENFORCEMENT: This file imports module/resource definitions from api_contract.py
as the single source of truth. Both frontend and backend use the same definitions.

This script creates:
1. All Module records
2. All Resource records (linked to modules)
3. RoleTemplatePermission records granting Super User all permissions

Run with: python -m app.seeds.init_resources
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.contracts import MODULES_AND_RESOURCES as CONTRACT_MODULES_AND_RESOURCES

# STRICT: Import from contract, NOT hardcoded here
# This ensures database always matches the contract
MODULES_AND_RESOURCES = CONTRACT_MODULES_AND_RESOURCES

# Resource-specific route paths (custom routes for certain resources)
# Maps resource name to frontend route path
RESOURCE_ROUTES = {
    # Personal
    "dashboard": "/",
    "my-tasks": "/my-tasks",
    "my-timesheet": "/my-timesheet",
    "my-expenses": "/my-expenses",
    "my-referrals": "/my-referrals",

    # Admin
    "users-access-control": "admin/users-access-control",
    "roles-permissions": "admin/roles-permissions",
    "admin-settings": "admin/admin-settings",
    "business-units": "admin/business-units",
    "certifications": "admin/certifications",
    "error-logs": "admin/error-log",
    "message-queue": "admin/messagequeue",
    "ticket-routing": "admin/ticket-routing",
    "ai-config": "admin/ai-config",
    "locale-currency": "settings/locale",
    "message-templates": "settings/templates",
    "slm-dashboard": "admin/slm-dashboard",
    "slm-training-data": "admin/slm-training",

    # Recruitment
    "candidate-review": "hm-candidate-review",
    "risk-dashboard": "recruiter/risk-dashboard",
    "thunder-analytics": "recruiter/thunder-analytics",
    "bulk-launch": "recruiter/bulk-launch",
    "intervention-queue": "recruiter/intervention-queue",
    "rehire-approval": "recruiter/rehire-approvals",
    "offer-letters": "offers",

    # Workforce
    "htd-intake": "htd-intake",
    "buddy-program": "buddy-program",
    "convert-to-employee": "employee-conversion",
    "allocations": "allocations",

    # Sales
    "clients": "client-management",
    "opportunities": "opportunity-pipeline",
    "sales-ops": "revenue",
    "partner-roi": "partner-roi",
    "demand-confirmation": "demand-confirmation",

    # Project Management
    "core-pull": "core-pull",
    "utilization-dashboard": "utilization-dashboard",
    "resource-forecast": "forecast",
    "forecast-vs-actual": "forecast-vs-actual",

    # Finance
    "invoice-management": "invoice-management",
    "finance-operations": "finance-operations",
    "executive-revenue-dashboard": "executive-revenue-dashboard",
    "revenue": "revenue",
    "forecasts": "forecast",

    # Reporting
    "bi-explorer": "bi-explorer",

    # Executive
    "ceo-dashboard": "ceo-fy-progress",
    "cfo-dashboard": "cfo-dashboard",
    "partner-dashboard": "troy-partner-dashboard",
    "bu-head-dashboard": "bu-head-dashboard",
    "executive-signal": "executive-signal",
    "admin-agent-state": "admin/agent-state-dashboard",
    "admin-weekly-recap": "admin/weekly-recap",
    "training-certification": "training-certification",

    # Executive Dashboards
    "ceo-dashboard-view": "ceo-fy-progress",
    "cfo-dashboard-view": "cfo-dashboard",
    "partner-dashboard-view": "troy-partner-dashboard",
    "bu-head-dashboard-view": "bu-head-dashboard",

    # AI & Automation
    "ask-thunder": "ai/thunder",
    "thunder-analytics": "ai/thunder-analytics",
    "ask-flash": "ai/flash",
    "ai-coaching": "ai/coaching",
}


def init_modules_and_resources(db: Session, tenant_id: int = 1):
    """Create all Module and Resource records."""

    print(f"Creating modules and resources for tenant_id={tenant_id}...")

    resource_count = 0

    for module_name, resource_names in MODULES_AND_RESOURCES.items():
        # Check if module exists
        module = db.query(Module).filter(
            Module.name == module_name,
            Module.tenant_id == tenant_id
        ).first()

        if not module:
            # Create module
            module = Module(
                name=module_name,
                display_name=module_name,
                description=f"{module_name} module",
                enabled=True,
                tenant_id=tenant_id
            )
            db.add(module)
            db.flush()  # Get the module ID
            print(f"  + Module: {module_name}")
        else:
            print(f"  OK Module: {module_name} already exists")

        # Create resources for this module
        for resource_name in resource_names:
            existing = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id
            ).first()

            if existing:
                print(f"    OK Resource: {resource_name}")
                continue

            # Use custom route if defined, otherwise use default /{resource_name}
            route_path = RESOURCE_ROUTES.get(resource_name, f"/{resource_name.replace('_', '-')}")

            resource = Resource(
                module_id=module.id,
                name=resource_name.replace("-", "_"),  # Store with underscores for consistency
                display_name=resource_name.replace("-", " ").title(),
                route_path=route_path,
                description=f"{resource_name} resource",
                enabled=True,
                tenant_id=tenant_id
            )
            db.add(resource)
            resource_count += 1
            print(f"    + Resource: {resource_name} -> {route_path}")

    db.commit()
    print(f"\nCreated {resource_count} resources\n")
    return resource_count


def make_personal_resources_mandatory(db: Session, tenant_id: int = 1):
    """Make Personal resources (dashboard, my-tasks, etc.) mandatory for all users."""

    print(f"Making Personal resources mandatory for all users...")

    # Get all role templates
    all_roles = db.query(RoleTemplate).filter(
        RoleTemplate.tenant_id == tenant_id,
        RoleTemplate.enabled == True
    ).all()

    print(f"  Found {len(all_roles)} role templates")

    # Get Personal module
    personal_module = db.query(Module).filter(
        Module.name == "Personal",
        Module.tenant_id == tenant_id
    ).first()

    if not personal_module:
        print("  ERROR: Personal module not found!")
        return 0

    # Get all Personal resources
    personal_resources = db.query(Resource).filter(
        Resource.module_id == personal_module.id,
        Resource.tenant_id == tenant_id,
        Resource.enabled == True
    ).all()

    print(f"  Found {len(personal_resources)} Personal resources")

    count = 0
    for role in all_roles:
        for resource in personal_resources:
            # Check if permission exists
            existing = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id == resource.id
            ).first()

            if not existing:
                # Grant at least VIEW permission
                permission = RoleTemplatePermission(
                    role_template_id=role.id,
                    resource_id=resource.id,
                    can_view=True,
                    can_create=False,
                    can_edit=False,
                    can_delete=False
                )
                db.add(permission)
                count += 1
            else:
                # Ensure VIEW is enabled
                if not existing.can_view:
                    existing.can_view = True
                    count += 1

    db.commit()
    print(f"  Granted Personal resource access to all roles ({count} new permissions)\n")
    return count


def main():
    """Initialize all modules and resources. Role template permissions are managed separately in the database."""

    db = SessionLocal()
    try:
        # Step 1: Create all modules and resources
        resource_count = init_modules_and_resources(db, tenant_id=1)

        # Step 2: Make Personal resources mandatory for all users
        mandatory_count = make_personal_resources_mandatory(db, tenant_id=1)

        print("=" * 70)
        print("SUCCESS: Resource Initialization Complete!")
        print("=" * 70)
        print(f"Resources created: {resource_count}")
        print(f"Personal resources made mandatory: {mandatory_count}")
        print("\nAll users now have mandatory access to Personal resources:")
        print("  - Dashboard")
        print("  - My Tasks")
        print("  - My Timesheet")
        print("  - My Expenses")
        print("  - My Referrals")
        print("\nRole template permissions are configured in the database, not seeded here.")
        print("=" * 70)

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"ERROR: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
