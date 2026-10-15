"""
Initialize all Modules, Resources, and grant Super User role full permissions.

STRICT CONTRACT ENFORCEMENT: This file imports module/resource definitions from api_contract.py
as the single source of truth. Both frontend and backend use the same definitions.

This script creates:
1. All Module records
2. All Resource records (linked to modules)
3. RoleTemplatePermission records granting Super User all permissions

Run with: python -m app.seeds.init_resources
"""
import logging
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.contracts import MODULES_AND_RESOURCES as CONTRACT_MODULES_AND_RESOURCES

# STRICT: Import from contract, NOT hardcoded here
# This ensures database always matches the contract
MODULES_AND_RESOURCES = CONTRACT_MODULES_AND_RESOURCES

# Resource -> frontend page. A resource listed here is a screen and appears in
# the nav menu (navigation.py); a resource NOT listed here is permission-only
# (e.g. dashboard-view grants) and never becomes a menu item. Every route must
# exist in frontend/src/routes/Approutes.jsx or AdminRoutes.jsx.
RESOURCE_ROUTES = {
    # Personal
    "dashboard": "/",
    "my-tasks": "/my-tasks",
    "my-timesheet": "/my-timesheet",
    "my-expenses": "/my-expenses",
    "my-referrals": "/my-referrals",
    # Recruitment
    "candidates": "/candidates",
    "jobs": "/jobs",
    "submissions": "/submissions",
    "offer-letters": "/offers-listing",
    "intervention-queue": "/recruiter/intervention-queue",
    "rehire-approval": "/recruiter/rehire-approvals",
    "thunder-analytics": "/recruiter/thunder-analytics",
    "checklists": "/checklist-templates",
    "candidate-review": "/hm-candidate-review",
    "risk-dashboard": "/recruiter/risk-dashboard",
    "bulk-launch": "/recruiter/bulk-launch",
    # Workforce
    "employees": "/employees",
    "allocations": "/allocations",
    "timesheets": "/timesheets",
    "htd-intake": "/htd-intake",
    "buddy-program": "/buddy-program",
    # the hiring pipeline (screen -> ... -> bench -> client); manual conversion stays at /employee-conversion
    "convert-to-employee": "/hiring-pipeline",
    "utilization-dashboard": "/utilization-dashboard",
    "resource-forecast": "/forecast",
    # bench / Staff Aug / Core: where every employee stands (CEO 2026-10-14)
    "workforce-overview": "/workforce",
    # Sales
    "clients": "/client-management",
    "opportunities": "/opportunity-pipeline",
    "sales-ops": "/revenue",
    "demand-confirmation": "/demand-confirmation",
    # Project Management
    "projects": "/projects",
    "core-pull": "/core-pull",
    # Finance
    "invoices": "/invoices",
    "forecasts": "/forecast",
    "finance-operations": "/finance-operations",
    "revenue": "/pnl",  # partner & org P&L (sales-ops keeps /revenue)
    # Reporting
    "bi-explorer": "/bi-explorer",
    # System
    "api-keys": "/api-keys",
    "error-logs": "/admin/error-log",
    "system-health": "/system-health",
    "slm-training-data": "/admin/slm-training",
    "message-queue": "/admin/messagequeue",
    "ticket-routing": "/admin/ticket-routing",
    "ai-config": "/admin/ai-config",
    "locale-currency": "/settings/locale",
    # Executive
    "ceo-dashboard": "/ceo-fy-progress",
    # FY goal tree (Org > Location > Partner > BU) + executive revenue; listed once, under Executive
    "goals": "/executive-revenue-dashboard",
    "cfo-dashboard": "/cfo-dashboard",
    "partner-dashboard": "/partner-dashboard",
    "executive-signal": "/executive-signal",
    "admin-agent-state": "/admin/agent-state-dashboard",
    "admin-weekly-recap": "/admin/weekly-recap",
    "bu-head-dashboard": "/bu-head-dashboard",
    # Admin
    "users-access-control": "/admin/users-access-control/users",
    "certifications": "/admin/certifications",
    "role-templates": "/admin/users-access-control/role-templates",
    "business-units": "/admin/users-access-control/business-units",
    "delivery-centers": "/admin/users-access-control/delivery-centers",
    "organizational-hierarchy": "/admin/users-access-control/organizational-hierarchy",
    # Executive Dashboards
    "ceo-dashboard-view": "/ceo-fy-progress",
    "cfo-dashboard-view": "/cfo-dashboard",
    "partner-dashboard-view": "/partner-dashboard",
    "bu-head-dashboard-view": "/bu-head-dashboard",
    # AI & Automation
    "ask-thunder": "/thunder",
    "slm-dashboard": "/admin/slm-dashboard",
}

# Menu labels where title-casing the resource name reads wrong
NAV_LABELS = {
    "convert-to-employee": "Hiring Pipeline",
    "revenue": "P&L (Partner & Org)",
    "goals": "Goals & Revenue",
    "ceo-dashboard": "CEO Dashboard",
    "cfo-dashboard": "CFO Dashboard",
    "bu-head-dashboard": "BU Head Dashboard",
    "ai-config": "AI Config",
    "api-keys": "API Keys",
    "slm-dashboard": "SLM Dashboard",
    "bi-explorer": "BI Explorer",
    "htd-intake": "HTD Intake",
    "my-tasks": "My Tasks",
    "workforce-overview": "Workforce Overview",
}

# Resources whose page is a tab of another page (Users & Access Control):
# they keep their route (deep links, permissions) but are not menu items.
# Extra screens governed by an existing resource's permission (no resource of their
# own): shown in the menu right after that resource for every role that can view it.
# The LinkedIn pipeline's endpoints all check "candidates", so its page does too --
# CEO, CFO, partners and BU heads see it under Recruitment, not only recruiters.
RESOURCE_EXTRA_PAGES = {
    "candidates": [{"key": "linkedin-pipeline", "label": "LinkedIn Pipeline", "route": "/linkedin-pipeline"}],
}

NAV_TAB_RESOURCES = {"role-templates", "business-units", "delivery-centers", "organizational-hierarchy"}


def init_modules_and_resources(db: Session, tenant_id: int = 1):
    """Create all Module and Resource records."""

    logger.info(f"Creating modules and resources for tenant_id={tenant_id}...")

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
            logger.info(f"  + Module: {module_name}")
        else:
            logger.info(f"  OK Module: {module_name} already exists")

        # Create resources for this module
        for resource_name in resource_names:
            existing = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id
            ).first()

            if existing:
                logger.info(f"    OK Resource: {resource_name}")
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
            logger.info(f"    + Resource: {resource_name} -> {route_path}")

    db.commit()
    logger.info(f"\nCreated {resource_count} resources\n")
    return resource_count

def make_personal_resources_mandatory(db: Session, tenant_id: int = 1):
    """Make Personal resources (dashboard, my-tasks, etc.) mandatory for all users."""

    logger.info("Making Personal resources mandatory for all users...")

    # Get all role templates
    all_roles = db.query(RoleTemplate).filter(
        RoleTemplate.tenant_id == tenant_id,
        RoleTemplate.enabled == True
    ).all()

    logger.info(f"  Found {len(all_roles)} role templates")

    # Get Personal module
    personal_module = db.query(Module).filter(
        Module.name == "Personal",
        Module.tenant_id == tenant_id
    ).first()

    if not personal_module:
        logger.info("  ERROR: Personal module not found!")
        return 0

    # Get all Personal resources
    personal_resources = db.query(Resource).filter(
        Resource.module_id == personal_module.id,
        Resource.tenant_id == tenant_id,
        Resource.enabled == True
    ).all()

    logger.info(f"  Found {len(personal_resources)} Personal resources")

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
    logger.info(f"  Granted Personal resource access to all roles ({count} new permissions)\n")
    return count

def main():
    """Initialize all modules and resources. Role template permissions are managed separately in the database."""

    db = SessionLocal()
    try:
        # Step 1: Create all modules and resources
        resource_count = init_modules_and_resources(db, tenant_id=1)

        # Step 2: Make Personal resources mandatory for all users
        mandatory_count = make_personal_resources_mandatory(db, tenant_id=1)

        logger.info("=" * 70)
        logger.info("SUCCESS: Resource Initialization Complete!")
        logger.info("=" * 70)
        logger.info(f"Resources created: {resource_count}")
        logger.info(f"Personal resources made mandatory: {mandatory_count}")
        logger.info("\nAll users now have mandatory access to Personal resources:")
        logger.info("  - Dashboard")
        logger.info("  - My Tasks")
        logger.info("  - My Timesheet")
        logger.info("  - My Expenses")
        logger.info("  - My Referrals")
        logger.info("\nRole template permissions are configured in the database, not seeded here.")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.info(f"ERROR: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
