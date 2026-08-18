"""
Initialize all Modules, Resources, and grant Super User role full permissions.

This script creates:
1. All Module records
2. All Resource records (linked to modules)
3. RoleTemplatePermission records granting Super User all permissions

Run with: python -m app.seeds.init_resources
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission

# All modules and their resources
MODULES_AND_RESOURCES = {
    "Admin": ["admin-settings", "users", "roles-permissions", "organization"],
    "Recruitment": [
        "candidates", "jobs", "submissions", "interviews",
        "offer-letters", "intervention-queue", "rehire-approval"
    ],
    "Workforce": [
        "employees", "onboarding", "allocations", "timesheets",
        "leave-management", "performance-management"
    ],
    "Sales": [
        "clients", "opportunities", "proposals", "revenue",
        "pipeline-management"
    ],
    "Project Management": [
        "projects", "tasks", "resources", "budget", "schedule"
    ],
    "Finance": [
        "invoices", "expenses", "payroll", "reports",
        "budget-management", "forecasts"
    ],
    "Reporting": [
        "analytics", "kpi-dashboard", "data-export", "scheduled-reports"
    ],
    "System": [
        "configuration", "api-keys", "webhooks", "audit-logs",
        "error-logs", "system-health"
    ],
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
            print(f"  ✓ Module: {module_name} already exists")

        # Create resources for this module
        for resource_name in resource_names:
            existing = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id
            ).first()

            if existing:
                print(f"    ✓ Resource: {resource_name}")
                continue

            resource = Resource(
                module_id=module.id,
                name=resource_name,
                display_name=resource_name.replace("-", " ").title(),
                description=f"{resource_name} resource",
                enabled=True,
                tenant_id=tenant_id
            )
            db.add(resource)
            resource_count += 1
            print(f"    + Resource: {resource_name}")

    db.commit()
    print(f"\nCreated {resource_count} resources\n")
    return resource_count


def grant_super_user_all_permissions(db: Session, tenant_id: int = 1):
    """Grant Super User role all V/C/E/D permissions on all resources."""

    print(f"Granting Super User all permissions...")

    # Get Super User role template
    super_user_role = db.query(RoleTemplate).filter(
        RoleTemplate.name.ilike("super user"),
        RoleTemplate.tenant_id == tenant_id
    ).first()

    if not super_user_role:
        print("  ERROR: Super User role not found!")
        return 0

    print(f"  Found Super User role (id={super_user_role.id})")

    # Get all resources
    all_resources = db.query(Resource).filter(
        Resource.tenant_id == tenant_id,
        Resource.enabled == True
    ).all()

    print(f"  Found {len(all_resources)} resources to grant permissions for")

    created_count = 0

    # Grant Super User all permissions for each resource
    for resource in all_resources:
        # Check if permission already exists
        existing = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == super_user_role.id,
            RoleTemplatePermission.resource_id == resource.id
        ).first()

        if existing:
            # Make sure all permissions are enabled
            existing.can_view = True
            existing.can_create = True
            existing.can_edit = True
            existing.can_delete = True
        else:
            # Create new permission record with all V/C/E/D enabled
            permission = RoleTemplatePermission(
                role_template_id=super_user_role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(permission)
            created_count += 1

    db.commit()
    print(f"  Granted {created_count} new permissions to Super User\n")
    return created_count


def main():
    """Initialize all modules, resources, and Super User permissions."""

    db = SessionLocal()
    try:
        # Step 1: Create all modules and resources
        resource_count = init_modules_and_resources(db, tenant_id=1)

        # Step 2: Grant Super User all permissions
        permission_count = grant_super_user_all_permissions(db, tenant_id=1)

        print("=" * 70)
        print("SUCCESS: Resource Initialization Complete!")
        print("=" * 70)
        print(f"Resources created: {resource_count}")
        print(f"Permissions granted to Super User: {permission_count}")
        print("\nSuper User now has FULL access to all modules and resources!")
        print("All permission errors should be resolved when you refresh the UI.")
        print("=" * 70)

    except Exception as e:
        print(f"ERROR: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
