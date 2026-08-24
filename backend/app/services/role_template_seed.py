"""
Role Template Seeding - Initialize role templates with permissions.

ZERO-HARDCODING: Seeds default role templates with permissions from
the new module×resource×action matrix system.

Call this at application startup to ensure role templates exist.
"""

from sqlalchemy.orm import Session
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.core.logging import logger


MODULES_SEED = [
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

RESOURCES_SEED = [
    # Recruitment Management module
    {"module": "recruitment_management", "name": "candidates", "display_name": "Candidates"},
    {"module": "recruitment_management", "name": "jobs", "display_name": "Job Postings"},
    {"module": "recruitment_management", "name": "interviews", "display_name": "Interviews"},
    {"module": "recruitment_management", "name": "offers", "display_name": "Offers"},

    # Finance & Revenue module
    {"module": "finance_revenue", "name": "invoices", "display_name": "Invoices"},
    {"module": "finance_revenue", "name": "financial_reports", "display_name": "Financial Reports"},
    {"module": "finance_revenue", "name": "billing", "display_name": "Billing"},

    # Workforce & Employees module
    {"module": "workforce_employees", "name": "employees", "display_name": "Employees"},
    {"module": "workforce_employees", "name": "timesheets", "display_name": "Timesheets"},
    {"module": "workforce_employees", "name": "allocations", "display_name": "Allocations"},

    # Administration module
    {"module": "administration", "name": "users", "display_name": "Users"},
    {"module": "administration", "name": "roles", "display_name": "Roles & Permissions"},
    {"module": "administration", "name": "business_units", "display_name": "Business Units"},
    {"module": "administration", "name": "settings", "display_name": "System Settings"},

    # Sales module
    {"module": "sales", "name": "opportunities", "display_name": "Sales Opportunities"},
    {"module": "sales", "name": "clients", "display_name": "Clients"},
    {"module": "sales", "name": "partners", "display_name": "Partners"},

    # Project Management module
    {"module": "project_management", "name": "projects", "display_name": "Projects"},
    {"module": "project_management", "name": "tasks", "display_name": "Tasks"},
    {"module": "project_management", "name": "deliverables", "display_name": "Deliverables"},

    # Reporting module
    {"module": "reporting", "name": "analytics", "display_name": "Analytics"},
    {"module": "reporting", "name": "dashboards", "display_name": "Dashboards"},
    {"module": "reporting", "name": "custom_reports", "display_name": "Custom Reports"},

    # System module
    {"module": "system", "name": "audit_logs", "display_name": "Audit Logs"},
    {"module": "system", "name": "system_config", "display_name": "System Configuration"},
    {"module": "system", "name": "maintenance", "display_name": "Maintenance"},

    # Executive Dashboards module
    {"module": "executive_dashboards", "name": "executive_overview", "display_name": "Executive Overview"},
    {"module": "executive_dashboards", "name": "kpi_metrics", "display_name": "KPI Metrics"},
    {"module": "executive_dashboards", "name": "financial_summary", "display_name": "Financial Summary"},

    # Engagement & Communications module
    {"module": "engagement_communications", "name": "campaigns", "display_name": "Engagement Campaigns"},
    {"module": "engagement_communications", "name": "messages", "display_name": "Messages"},
    {"module": "engagement_communications", "name": "notifications", "display_name": "Notifications"},
]

# role_name → resource.action → True/False
ROLE_TEMPLATE_PERMISSIONS = {
    "Super User": {
        # Recruitment Management - Full access
        "candidates": {"view": True, "create": True, "edit": True, "delete": True},
        "jobs": {"view": True, "create": True, "edit": True, "delete": True},
        "interviews": {"view": True, "create": True, "edit": True, "delete": True},
        "offers": {"view": True, "create": True, "edit": True, "delete": True},
        # Finance & Revenue - Full access
        "invoices": {"view": True, "create": True, "edit": True, "delete": True},
        "financial_reports": {"view": True, "create": True, "edit": True, "delete": True},
        "billing": {"view": True, "create": True, "edit": True, "delete": True},
        # Workforce & Employees - Full access
        "employees": {"view": True, "create": True, "edit": True, "delete": True},
        "timesheets": {"view": True, "create": True, "edit": True, "delete": True},
        "allocations": {"view": True, "create": True, "edit": True, "delete": True},
        # Administration - Full access
        "users": {"view": True, "create": True, "edit": True, "delete": True},
        "roles": {"view": True, "create": True, "edit": True, "delete": True},
        "business_units": {"view": True, "create": True, "edit": True, "delete": True},
        "settings": {"view": True, "create": True, "edit": True, "delete": True},
        # Sales - Full access
        "opportunities": {"view": True, "create": True, "edit": True, "delete": True},
        "clients": {"view": True, "create": True, "edit": True, "delete": True},
        "partners": {"view": True, "create": True, "edit": True, "delete": True},
        # Project Management - Full access
        "projects": {"view": True, "create": True, "edit": True, "delete": True},
        "tasks": {"view": True, "create": True, "edit": True, "delete": True},
        "deliverables": {"view": True, "create": True, "edit": True, "delete": True},
        # Reporting - Full access
        "analytics": {"view": True, "create": True, "edit": True, "delete": True},
        "dashboards": {"view": True, "create": True, "edit": True, "delete": True},
        "custom_reports": {"view": True, "create": True, "edit": True, "delete": True},
        # System - Full access
        "audit_logs": {"view": True, "create": True, "edit": True, "delete": True},
        "system_config": {"view": True, "create": True, "edit": True, "delete": True},
        "maintenance": {"view": True, "create": True, "edit": True, "delete": True},
        # Executive Dashboards - Full access
        "executive_overview": {"view": True, "create": True, "edit": True, "delete": True},
        "kpi_metrics": {"view": True, "create": True, "edit": True, "delete": True},
        "financial_summary": {"view": True, "create": True, "edit": True, "delete": True},
        # Engagement & Communications - Full access
        "campaigns": {"view": True, "create": True, "edit": True, "delete": True},
        "messages": {"view": True, "create": True, "edit": True, "delete": True},
        "notifications": {"view": True, "create": True, "edit": True, "delete": True},
    },
    "Recruiter": {
        # Recruitment Management - Full access
        "candidates": {"view": True, "create": True, "edit": True, "delete": False},
        "jobs": {"view": True, "create": False, "edit": False, "delete": False},
        "interviews": {"view": True, "create": True, "edit": True, "delete": False},
        "offers": {"view": True, "create": True, "edit": True, "delete": False},
        # Finance & Revenue - View only
        "invoices": {"view": True, "create": False, "edit": False, "delete": False},
        "financial_reports": {"view": True, "create": False, "edit": False, "delete": False},
        "billing": {"view": True, "create": False, "edit": False, "delete": False},
        # Workforce & Employees - No access
        "employees": {"view": False, "create": False, "edit": False, "delete": False},
        "timesheets": {"view": False, "create": False, "edit": False, "delete": False},
        "allocations": {"view": False, "create": False, "edit": False, "delete": False},
        # Administration - View only
        "users": {"view": True, "create": False, "edit": False, "delete": False},
        "roles": {"view": False, "create": False, "edit": False, "delete": False},
        "business_units": {"view": True, "create": False, "edit": False, "delete": False},
        "settings": {"view": False, "create": False, "edit": False, "delete": False},
        # Sales - View only
        "opportunities": {"view": True, "create": False, "edit": False, "delete": False},
        "clients": {"view": True, "create": False, "edit": False, "delete": False},
        "partners": {"view": True, "create": False, "edit": False, "delete": False},
        # Project Management - No access
        "projects": {"view": False, "create": False, "edit": False, "delete": False},
        "tasks": {"view": False, "create": False, "edit": False, "delete": False},
        "deliverables": {"view": False, "create": False, "edit": False, "delete": False},
        # Reporting - View only
        "analytics": {"view": True, "create": False, "edit": False, "delete": False},
        "dashboards": {"view": True, "create": False, "edit": False, "delete": False},
        "custom_reports": {"view": False, "create": False, "edit": False, "delete": False},
        # System - No access
        "audit_logs": {"view": False, "create": False, "edit": False, "delete": False},
        "system_config": {"view": False, "create": False, "edit": False, "delete": False},
        "maintenance": {"view": False, "create": False, "edit": False, "delete": False},
        # Executive Dashboards - No access
        "executive_overview": {"view": False, "create": False, "edit": False, "delete": False},
        "kpi_metrics": {"view": False, "create": False, "edit": False, "delete": False},
        "financial_summary": {"view": False, "create": False, "edit": False, "delete": False},
        # Engagement & Communications - View only
        "campaigns": {"view": True, "create": False, "edit": False, "delete": False},
        "messages": {"view": True, "create": False, "edit": False, "delete": False},
        "notifications": {"view": True, "create": False, "edit": False, "delete": False},
    },
    "HR Manager": {
        # Recruitment Management - Most access
        "candidates": {"view": True, "create": True, "edit": True, "delete": False},
        "jobs": {"view": True, "create": True, "edit": True, "delete": False},
        "interviews": {"view": True, "create": True, "edit": True, "delete": False},
        "offers": {"view": True, "create": True, "edit": True, "delete": False},
        # Finance & Revenue - View only
        "invoices": {"view": True, "create": False, "edit": False, "delete": False},
        "financial_reports": {"view": True, "create": False, "edit": False, "delete": False},
        "billing": {"view": True, "create": False, "edit": False, "delete": False},
        # Workforce & Employees - Full access
        "employees": {"view": True, "create": True, "edit": True, "delete": False},
        "timesheets": {"view": True, "create": False, "edit": False, "delete": False},
        "allocations": {"view": True, "create": True, "edit": True, "delete": False},
        # Administration - Limited
        "users": {"view": True, "create": True, "edit": True, "delete": False},
        "roles": {"view": True, "create": False, "edit": False, "delete": False},
        "business_units": {"view": True, "create": False, "edit": False, "delete": False},
        "settings": {"view": False, "create": False, "edit": False, "delete": False},
        # Sales - View only
        "opportunities": {"view": True, "create": False, "edit": False, "delete": False},
        "clients": {"view": True, "create": False, "edit": False, "delete": False},
        "partners": {"view": True, "create": False, "edit": False, "delete": False},
        # Project Management - View only
        "projects": {"view": True, "create": False, "edit": False, "delete": False},
        "tasks": {"view": True, "create": False, "edit": False, "delete": False},
        "deliverables": {"view": True, "create": False, "edit": False, "delete": False},
        # Reporting - Full access
        "analytics": {"view": True, "create": True, "edit": True, "delete": False},
        "dashboards": {"view": True, "create": True, "edit": True, "delete": False},
        "custom_reports": {"view": True, "create": True, "edit": True, "delete": False},
        # System - No access
        "audit_logs": {"view": False, "create": False, "edit": False, "delete": False},
        "system_config": {"view": False, "create": False, "edit": False, "delete": False},
        "maintenance": {"view": False, "create": False, "edit": False, "delete": False},
        # Executive Dashboards - No access
        "executive_overview": {"view": False, "create": False, "edit": False, "delete": False},
        "kpi_metrics": {"view": False, "create": False, "edit": False, "delete": False},
        "financial_summary": {"view": False, "create": False, "edit": False, "delete": False},
        # Engagement & Communications - Full access
        "campaigns": {"view": True, "create": True, "edit": True, "delete": False},
        "messages": {"view": True, "create": True, "edit": True, "delete": False},
        "notifications": {"view": True, "create": True, "edit": True, "delete": False},
    },
    "Finance Manager": {
        # Recruitment Management - View only
        "candidates": {"view": True, "create": False, "edit": False, "delete": False},
        "jobs": {"view": True, "create": False, "edit": False, "delete": False},
        "interviews": {"view": False, "create": False, "edit": False, "delete": False},
        "offers": {"view": True, "create": False, "edit": False, "delete": False},
        # Finance & Revenue - Full access
        "invoices": {"view": True, "create": True, "edit": True, "delete": False},
        "financial_reports": {"view": True, "create": True, "edit": True, "delete": False},
        "billing": {"view": True, "create": True, "edit": True, "delete": False},
        # Workforce & Employees - View only
        "employees": {"view": True, "create": False, "edit": False, "delete": False},
        "timesheets": {"view": True, "create": False, "edit": False, "delete": False},
        "allocations": {"view": True, "create": False, "edit": False, "delete": False},
        # Administration - View only
        "users": {"view": True, "create": False, "edit": False, "delete": False},
        "roles": {"view": False, "create": False, "edit": False, "delete": False},
        "business_units": {"view": True, "create": False, "edit": False, "delete": False},
        "settings": {"view": False, "create": False, "edit": False, "delete": False},
        # Sales - View only
        "opportunities": {"view": True, "create": False, "edit": False, "delete": False},
        "clients": {"view": True, "create": False, "edit": False, "delete": False},
        "partners": {"view": True, "create": False, "edit": False, "delete": False},
        # Project Management - No access
        "projects": {"view": False, "create": False, "edit": False, "delete": False},
        "tasks": {"view": False, "create": False, "edit": False, "delete": False},
        "deliverables": {"view": False, "create": False, "edit": False, "delete": False},
        # Reporting - Full access
        "analytics": {"view": True, "create": True, "edit": True, "delete": False},
        "dashboards": {"view": True, "create": True, "edit": True, "delete": False},
        "custom_reports": {"view": True, "create": True, "edit": True, "delete": False},
        # System - No access
        "audit_logs": {"view": False, "create": False, "edit": False, "delete": False},
        "system_config": {"view": False, "create": False, "edit": False, "delete": False},
        "maintenance": {"view": False, "create": False, "edit": False, "delete": False},
        # Executive Dashboards - View only
        "executive_overview": {"view": True, "create": False, "edit": False, "delete": False},
        "kpi_metrics": {"view": True, "create": False, "edit": False, "delete": False},
        "financial_summary": {"view": True, "create": False, "edit": False, "delete": False},
        # Engagement & Communications - No access
        "campaigns": {"view": False, "create": False, "edit": False, "delete": False},
        "messages": {"view": False, "create": False, "edit": False, "delete": False},
        "notifications": {"view": False, "create": False, "edit": False, "delete": False},
    },
    "Admin": {
        # Recruitment Management - View only
        "candidates": {"view": True, "create": False, "edit": False, "delete": False},
        "jobs": {"view": True, "create": False, "edit": False, "delete": False},
        "interviews": {"view": True, "create": False, "edit": False, "delete": False},
        "offers": {"view": True, "create": False, "edit": False, "delete": False},
        # Finance & Revenue - View only
        "invoices": {"view": True, "create": False, "edit": False, "delete": False},
        "financial_reports": {"view": True, "create": False, "edit": False, "delete": False},
        "billing": {"view": True, "create": False, "edit": False, "delete": False},
        # Workforce & Employees - View only
        "employees": {"view": True, "create": False, "edit": False, "delete": False},
        "timesheets": {"view": True, "create": False, "edit": False, "delete": False},
        "allocations": {"view": True, "create": False, "edit": False, "delete": False},
        # Administration - Full access
        "users": {"view": True, "create": True, "edit": True, "delete": True},
        "roles": {"view": True, "create": True, "edit": True, "delete": True},
        "business_units": {"view": True, "create": True, "edit": True, "delete": True},
        "settings": {"view": True, "create": True, "edit": True, "delete": True},
        # Sales - View only
        "opportunities": {"view": True, "create": False, "edit": False, "delete": False},
        "clients": {"view": True, "create": False, "edit": False, "delete": False},
        "partners": {"view": True, "create": False, "edit": False, "delete": False},
        # Project Management - View only
        "projects": {"view": True, "create": False, "edit": False, "delete": False},
        "tasks": {"view": True, "create": False, "edit": False, "delete": False},
        "deliverables": {"view": True, "create": False, "edit": False, "delete": False},
        # Reporting - Full access
        "analytics": {"view": True, "create": True, "edit": True, "delete": False},
        "dashboards": {"view": True, "create": True, "edit": True, "delete": False},
        "custom_reports": {"view": True, "create": True, "edit": True, "delete": False},
        # System - Full access
        "audit_logs": {"view": True, "create": True, "edit": True, "delete": False},
        "system_config": {"view": True, "create": True, "edit": True, "delete": True},
        "maintenance": {"view": True, "create": True, "edit": True, "delete": True},
        # Executive Dashboards - View only
        "executive_overview": {"view": True, "create": False, "edit": False, "delete": False},
        "kpi_metrics": {"view": True, "create": False, "edit": False, "delete": False},
        "financial_summary": {"view": True, "create": False, "edit": False, "delete": False},
        # Engagement & Communications - View only
        "campaigns": {"view": True, "create": False, "edit": False, "delete": False},
        "messages": {"view": True, "create": False, "edit": False, "delete": False},
        "notifications": {"view": True, "create": False, "edit": False, "delete": False},
    },
}


def assign_users_to_role_templates(db: Session, tenant_id: int = 1) -> None:
    """
    Assign existing users to role templates based on their UserRole string.

    This bridges the gap between the old role system (UserRole string) and
    the new role template system (RoleTemplate records).

    Process:
    1. Query all users with a UserRole string
    2. Find matching RoleTemplate by name
    3. Create UserRole record linking user to role template
    4. Skip if user already has a UserRole record (idempotent)

    Args:
        db: Database session
        tenant_id: Tenant ID for multi-tenancy (default: 1)
    """
    try:
        from app.models.user import Users

        # Migration: Assign users without role_template_id to a default template
        # Users now have direct role_template_id column instead of UserRole junction table
        users_without_template = db.query(Users).filter(
            Users.role_template_id.is_(None)
        ).all()

        # If there are users without templates, assign them to Recruiter template
        if users_without_template:
            recruiter_template = db.query(RoleTemplate).filter(
                RoleTemplate.name == "Recruiter",
                RoleTemplate.tenant_id == tenant_id
            ).first()

            if recruiter_template:
                for user in users_without_template:
                    user.role_template_id = recruiter_template.id

                db.commit()

        logger.info("[OK] Existing users assigned to role templates")

    except Exception as exc:
        logger.error(f"Failed to assign users to role templates: {exc}")
        db.rollback()
        # Don't raise — if assignment fails, system can still work with legacy fallback


def seed_role_templates(db: Session, tenant_id: int = 1) -> None:
    """
    Idempotently seed all modules, resources, and role templates.
    Called at application startup.

    Args:
        db: Database session
        tenant_id: Tenant ID for multi-tenancy (default: 1)
    """
    try:
        # First, assign existing users to role templates
        assign_users_to_role_templates(db, tenant_id)
        # 1. Seed modules
        module_map = {}
        for mod_data in MODULES_SEED:
            existing = db.query(Module).filter(
                Module.name == mod_data["name"],
                Module.tenant_id == tenant_id
            ).first()
            if not existing:
                mod = Module(
                    name=mod_data["name"],
                    display_name=mod_data["display_name"],
                    tenant_id=tenant_id
                )
                db.add(mod)
                db.flush()
                module_map[mod.name] = mod
            else:
                module_map[existing.name] = existing

        # 2. Seed resources
        resource_map = {}
        for res_data in RESOURCES_SEED:
            module = module_map.get(res_data["module"])
            if not module:
                continue

            existing = db.query(Resource).filter(
                Resource.name == res_data["name"],
                Resource.module_id == module.id,
                Resource.tenant_id == tenant_id
            ).first()
            if not existing:
                res = Resource(
                    name=res_data["name"],
                    display_name=res_data["display_name"],
                    module_id=module.id,
                    tenant_id=tenant_id
                )
                db.add(res)
                db.flush()
                resource_map[f"{res_data['module']}.{res.name}"] = res
            else:
                resource_map[f"{res_data['module']}.{res_data['name']}"] = existing

        # 3. Seed role templates
        for role_name, permissions in ROLE_TEMPLATE_PERMISSIONS.items():
            existing_role = db.query(RoleTemplate).filter(
                RoleTemplate.name == role_name,
                RoleTemplate.tenant_id == tenant_id
            ).first()
            if not existing_role:
                role = RoleTemplate(
                    name=role_name,
                    display_name=role_name,
                    is_system=True,
                    tenant_id=tenant_id,
                    created_by="system"
                )
                db.add(role)
                db.flush()
            else:
                role = existing_role

            # 4. Seed role-resource permissions
            for resource_name, actions in permissions.items():
                # Find module for this resource
                module_name = None
                for mod_data in MODULES_SEED:
                    if any(r["name"] == resource_name and r["module"] == mod_data["name"] for r in RESOURCES_SEED):
                        module_name = mod_data["name"]
                        break

                if not module_name:
                    continue

                key = f"{module_name}.{resource_name}"
                resource = resource_map.get(key)
                if not resource:
                    continue

                # Check if permission already exists
                existing_perm = db.query(RoleTemplatePermission).filter(
                    RoleTemplatePermission.role_template_id == role.id,
                    RoleTemplatePermission.resource_id == resource.id
                ).first()

                if not existing_perm:
                    perm = RoleTemplatePermission(
                        role_template_id=role.id,
                        resource_id=resource.id,
                        can_view=actions.get("view", False),
                        can_create=actions.get("create", False),
                        can_edit=actions.get("edit", False),
                        can_delete=actions.get("delete", False)
                    )
                    db.add(perm)

        db.commit()
        logger.info("[OK] Role templates seeded successfully (modules, resources, permissions)")

    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to seed role templates: {exc}")
        raise
