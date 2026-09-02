#!/usr/bin/env python3
"""
BOOTSTRAP ONLY: Grant Super User all permissions ONCE.
After this, all permissions are managed dynamically via templates (no hardcoding).
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
    print("[BOOTSTRAP: Super User Permissions Only]")
    print("="*60 + "\n")

    # Get default tenant
    tenants = db.query(Tenant).all()
    print(f"Found {len(tenants)} tenant(s)")

    for tenant in tenants:
        print(f"\nTenant: {tenant.name} (id={tenant.id})")

        # Find Super User role
        super_user = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Super User",
            RoleTemplate.tenant_id == tenant.id
        ).first()

        if not super_user:
            print("  ⚠️  Super User role not found, skipping")
            continue

        # Get all resources in this tenant
        resources = db.query(Resource).filter(
            Resource.tenant_id == tenant.id
        ).all()

        if not resources:
            print(f"  ⚠️  No resources found")
            continue

        print(f"  Resources found: {len(resources)}")

        # Count existing permissions for Super User
        existing_count = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == super_user.id
        ).count()

        if existing_count >= len(resources):
            print(f"  ✅ Super User already has all {existing_count} permissions")
            continue

        print(f"  Super User currently has {existing_count} permissions")
        print(f"  Granting all {len(resources)} resources...")

        # Grant Super User all permissions
        for resource in resources:
            exists = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == super_user.id,
                RoleTemplatePermission.resource_id == resource.id
            ).first()

            if not exists:
                perm = RoleTemplatePermission(
                    role_template_id=super_user.id,
                    resource_id=resource.id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True,
                    created_at=datetime.utcnow()
                )
                db.add(perm)

        db.commit()
        print(f"  ✅ Super User now has full access to all resources")

    print("\n" + "="*60)
    print("✅ BOOTSTRAP COMPLETE")
    print("="*60)
    print("\nSuper User now has full permissions.")
    print("All other roles are managed dynamically via UI - NO HARDCODING!")
    print("When admins create new roles via UI, they select permissions there.")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
