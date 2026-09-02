#!/usr/bin/env python3
"""
Fix all role template permissions at once.
Ensures every role has permissions for all resources.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission
from app.models.tenant import Tenant
from datetime import datetime

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[Permission Fix] Starting permission audit and repair...\n")

    # Get the default tenant
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
    if not tenant:
        raise Exception("Tenant not found")

    tenant_id = tenant.id
    print(f"[1] Working with tenant: {tenant.name} (id={tenant_id})")

    # Get all resources for this tenant
    resources = db.query(Resource).filter(Resource.tenant_id == tenant_id).all()
    print(f"[2] Found {len(resources)} resources in database")

    # Get all role templates
    roles = db.query(RoleTemplate).filter(RoleTemplate.tenant_id == tenant_id).all()
    print(f"[3] Found {len(roles)} role templates")

    # For each role template, ensure it has permissions for all resources
    fixed_count = 0
    for role in roles:
        existing_perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role.id
        ).count()

        missing_count = len(resources) - existing_perms

        if missing_count > 0:
            print(f"\n   {role.name}:")
            print(f"     Has {existing_perms}/{len(resources)} permissions")

            # Add missing permissions
            for resource in resources:
                # Check if permission already exists
                exists = db.query(RoleTemplatePermission).filter(
                    RoleTemplatePermission.role_template_id == role.id,
                    RoleTemplatePermission.resource_id == resource.id
                ).first()

                if not exists:
                    # Determine permissions based on role name
                    if role.name == "Super User":
                        can_view = can_create = can_edit = can_delete = True
                    elif role.name in ["Admin", "CEO", "CFO", "Partner"]:
                        can_view = can_create = can_edit = True
                        can_delete = resource.name not in ["audit_logs"]  # Don't delete audit logs
                    elif role.name in ["HR Manager", "BU Head"]:
                        can_view = can_create = can_edit = True
                        can_delete = resource.name in ["candidates", "employees"]
                    elif role.name == "Recruiter":
                        can_view = can_create = can_edit = True
                        can_delete = False
                    else:
                        # Default: view only
                        can_view = True
                        can_create = can_edit = can_delete = False

                    perm = RoleTemplatePermission(
                        role_template_id=role.id,
                        resource_id=resource.id,
                        can_view=can_view,
                        can_create=can_create,
                        can_edit=can_edit,
                        can_delete=can_delete,
                        created_at=datetime.utcnow()
                    )
                    db.add(perm)
                    fixed_count += 1

            print(f"     ✅ Added {missing_count} missing permissions")
        else:
            print(f"\n   {role.name}: ✅ Complete ({existing_perms} permissions)")

    db.commit()

    print(f"\n[SUCCESS] Fixed {fixed_count} missing permissions")
    print("\nPermission status by role:")
    for role in roles:
        perm_count = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role.id
        ).count()
        print(f"  • {role.name}: {perm_count}/{len(resources)} permissions")

    print("\n" + "="*60)
    print("✅ ALL ROLES NOW HAVE COMPLETE PERMISSIONS")
    print("="*60)
    print("\nNext steps:")
    print("1. Restart backend")
    print("2. ALL users will now see navigation automatically")
    print("3. No more 'blank navigation' issues")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
