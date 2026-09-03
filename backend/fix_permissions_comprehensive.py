#!/usr/bin/env python3
"""
COMPREHENSIVE FIX: Grant all permissions to all roles for ALL tenants.
This is the one-time fix to solve permission issues for every user, every role.
"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission
from app.models.tenant import Tenant
from datetime import datetime

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[COMPREHENSIVE PERMISSION FIX]")
    print("="*60)
    print("Granting all resources to all roles for all tenants...\n")

    # Get all tenants
    tenants = db.query(Tenant).all()
    print(f"[1] Found {len(tenants)} tenant(s)\n")

    total_fixed = 0

    for tenant in tenants:
        print(f"Processing tenant: {tenant.name} (id={tenant.id})")

        # Get all resources for this tenant
        resources = db.query(Resource).filter(Resource.tenant_id == tenant.id).all()
        print(f"  Resources in this tenant: {len(resources)}")

        if len(resources) == 0:
            print(f"  ⚠️  No resources found, skipping tenant")
            continue

        # Get all role templates
        roles = db.query(RoleTemplate).filter(RoleTemplate.tenant_id == tenant.id).all()
        print(f"  Role templates in this tenant: {len(roles)}\n")

        # For each role, grant all resources
        for role in roles:
            existing_perms = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id
            ).count()

            missing = len(resources) - existing_perms

            if missing > 0:
                print(f"    {role.name}:")
                print(f"      Has {existing_perms}/{len(resources)} permissions")

                # Grant missing permissions
                for resource in resources:
                    exists = db.query(RoleTemplatePermission).filter(
                        RoleTemplatePermission.role_template_id == role.id,
                        RoleTemplatePermission.resource_id == resource.id
                    ).first()

                    if not exists:
                        # Determine permissions based on role
                        if role.name == "Super User":
                            can_view = can_create = can_edit = can_delete = True
                        elif role.name in ["Admin", "CEO", "CFO", "Partner"]:
                            can_view = can_create = can_edit = True
                            can_delete = resource.name not in ["audit_logs", "audit-logs", "error_logs", "error-logs"]
                        elif role.name in ["HR Manager", "BU Head"]:
                            can_view = can_create = can_edit = True
                            can_delete = resource.name in ["candidates", "employees"]
                        elif role.name in ["Recruiter", "Employee"]:
                            can_view = can_create = can_edit = True
                            can_delete = False
                        else:
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
                        total_fixed += 1

                print(f"      ✅ Added {missing} missing permissions\n")
            else:
                print(f"    {role.name}: ✅ Complete\n")

        db.commit()

    print("="*60)
    print(f"✅ FIXED {total_fixed} TOTAL PERMISSIONS")
    print("="*60)
    print("\nAll roles now have complete permission coverage!")
    print("Every user will see proper navigation on next login.")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
