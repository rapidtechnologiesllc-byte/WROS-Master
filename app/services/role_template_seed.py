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
    {"name": "Recruitment", "display_name": "Recruitment Management"},
    {"name": "Workforce", "display_name": "Workforce & Employees"},
    {"name": "Finance", "display_name": "Finance & Revenue"},
    {"name": "Admin", "display_name": "System Administration"},
]

RESOURCES_SEED = [
    # Recruitment module
    {"module": "Recruitment", "name": "candidates", "display_name": "Candidates"},
    {"module": "Recruitment", "name": "jobs", "display_name": "Job Postings"},
    {"module": "Recruitment", "name": "interviews", "display_name": "Interviews"},
    {"module": "Recruitment", "name": "offers", "display_name": "Offers"},

    # Workforce module
    {"module": "Workforce", "name": "employees", "display_name": "Employees"},
    {"module": "Workforce", "name": "timesheets", "display_name": "Timesheets"},

    # Finance module
    {"module": "Finance", "name": "invoices", "display_name": "Invoices"},
    {"module": "Finance", "name": "reports", "display_name": "Financial Reports"},

    # Admin module
    {"module": "Admin", "name": "users", "display_name": "Users"},
    {"module": "Admin", "name": "roles", "display_name": "Roles & Permissions"},
]

# role_name → resource.action → True/False
ROLE_TEMPLATE_PERMISSIONS = {
    "Super User": {
        "candidates": {"view": True, "create": True, "edit": True, "delete": True},
        "jobs": {"view": True, "create": True, "edit": True, "delete": True},
        "interviews": {"view": True, "create": True, "edit": True, "delete": True},
        "offers": {"view": True, "create": True, "edit": True, "delete": True},
        "employees": {"view": True, "create": True, "edit": True, "delete": True},
        "timesheets": {"view": True, "create": True, "edit": True, "delete": True},
        "invoices": {"view": True, "create": True, "edit": True, "delete": True},
        "reports": {"view": True, "create": True, "edit": True, "delete": True},
        "users": {"view": True, "create": True, "edit": True, "delete": True},
        "roles": {"view": True, "create": True, "edit": True, "delete": True},
    },
    "Recruiter": {
        "candidates": {"view": True, "create": True, "edit": True, "delete": False},
        "jobs": {"view": True, "create": False, "edit": False, "delete": False},
        "interviews": {"view": True, "create": True, "edit": True, "delete": False},
        "offers": {"view": True, "create": True, "edit": True, "delete": False},
        "employees": {"view": False, "create": False, "edit": False, "delete": False},
        "timesheets": {"view": False, "create": False, "edit": False, "delete": False},
        "invoices": {"view": False, "create": False, "edit": False, "delete": False},
        "reports": {"view": False, "create": False, "edit": False, "delete": False},
        "users": {"view": False, "create": False, "edit": False, "delete": False},
        "roles": {"view": False, "create": False, "edit": False, "delete": False},
    },
    "HR Manager": {
        "candidates": {"view": True, "create": True, "edit": True, "delete": False},
        "jobs": {"view": True, "create": True, "edit": True, "delete": False},
        "interviews": {"view": True, "create": True, "edit": True, "delete": False},
        "offers": {"view": True, "create": True, "edit": True, "delete": False},
        "employees": {"view": True, "create": True, "edit": True, "delete": False},
        "timesheets": {"view": True, "create": False, "edit": False, "delete": False},
        "invoices": {"view": False, "create": False, "edit": False, "delete": False},
        "reports": {"view": False, "create": False, "edit": False, "delete": False},
        "users": {"view": True, "create": True, "edit": True, "delete": False},
        "roles": {"view": False, "create": False, "edit": False, "delete": False},
    },
    "Hiring Manager": {
        "candidates": {"view": True, "create": False, "edit": False, "delete": False},
        "jobs": {"view": True, "create": False, "edit": False, "delete": False},
        "interviews": {"view": True, "create": True, "edit": True, "delete": False},
        "offers": {"view": True, "create": False, "edit": False, "delete": False},
        "employees": {"view": False, "create": False, "edit": False, "delete": False},
        "timesheets": {"view": False, "create": False, "edit": False, "delete": False},
        "invoices": {"view": False, "create": False, "edit": False, "delete": False},
        "reports": {"view": False, "create": False, "edit": False, "delete": False},
        "users": {"view": False, "create": False, "edit": False, "delete": False},
        "roles": {"view": False, "create": False, "edit": False, "delete": False},
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
        from app.models.user import Users, UserRole

        # Get all users who don't yet have a UserRole record (new system)
        users_without_template = db.query(Users).filter(
            Users.UserRole.isnot(None),
            ~Users.id.in_(
                db.query(UserRole.user_id).filter(UserRole.tenant_id == tenant_id)
            )
        ).all()

        for user in users_without_template:
            if not user.UserRole:
                continue

            # Find role template with matching name
            role_template = db.query(RoleTemplate).filter(
                RoleTemplate.name == user.UserRole,
                RoleTemplate.tenant_id == tenant_id
            ).first()

            if not role_template:
                logger.warning(f"No role template found for user role: {user.UserRole}")
                continue

            # Create UserRole record
            user_role = UserRole(
                user_id=user.UserID,
                role_template_id=role_template.id,
                business_unit_id=user.business_unit_id,
                tenant_id=tenant_id
            )
            db.add(user_role)

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
                resource_map[f"{res_data['module']}.{res.name}"] = existing

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
