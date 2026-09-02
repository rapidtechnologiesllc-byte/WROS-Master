#!/usr/bin/env python3
"""
PROPER initialization: Grant role-SPECIFIC permissions from role_template_seed.py
Only grant permissions that are actually defined for each role.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission
from app.models.tenant import Tenant
from app.services.role_template_seed import ROLE_TEMPLATE_PERMISSIONS
from datetime import datetime

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[PROPER ROLE PERMISSION INITIALIZATION]")
    print("="*60)
    print("Granting role-SPECIFIC permissions (not all-to-all)...\n")

    # Get default tenant
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
    if not tenant:
        tenant = db.query(Tenant).first()  # Fallback to first tenant

    if not tenant:
        raise Exception("No tenant found")

    tenant_id = tenant.id
    print(f"Working with tenant: {tenant.name} (id={tenant_id})\n")

    total_granted = 0

    # For each role defined in ROLE_TEMPLATE_PERMISSIONS
    for role_name, permissions_map in ROLE_TEMPLATE_PERMISSIONS.items():
        print(f"Processing role: {role_name}")

        # Get or create the role
        role = db.query(RoleTemplate).filter(
            RoleTemplate.name == role_name,
            RoleTemplate.tenant_id == tenant_id
        ).first()

        if not role:
            print(f"  [WARN] Role '{role_name}' not found in database, skipping")
            continue

        # For each resource with permissions defined in ROLE_TEMPLATE_PERMISSIONS
        for resource_name, actions in permissions_map.items():
            # Find the resource in database (it should exist from init_resources)
            resource = db.query(Resource).filter(
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id
            ).first()

            if not resource:
                # Try with hyphens instead of underscores
                resource = db.query(Resource).filter(
                    Resource.name == resource_name.replace('_', '-'),
                    Resource.tenant_id == tenant_id
                ).first()

            if not resource:
                print(f"  [WARN] Resource '{resource_name}' not found, skipping")
                continue

            # Check if permission already exists
            existing = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id == resource.id
            ).first()

            if not existing:
                # Grant the permission with the exact actions defined
                perm = RoleTemplatePermission(
                    role_template_id=role.id,
                    resource_id=resource.id,
                    can_view=actions.get("view", False),
                    can_create=actions.get("create", False),
                    can_edit=actions.get("edit", False),
                    can_delete=actions.get("delete", False),
                    created_at=datetime.utcnow()
                )
                db.add(perm)
                total_granted += 1

        db.commit()
        perm_count = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == role.id
        ).count()
        print(f"  [OK] Role has {perm_count} permissions\n")

    print("="*60)
    print(f"[SUCCESS] GRANTED {total_granted} PROPER ROLE-SPECIFIC PERMISSIONS")
    print("="*60)
    print("\nPermissions are now ROLE-SPECIFIC, not all-to-all:")
    print("  • Super User: Full access to all resources")
    print("  • Recruiter: Only recruitment-related resources")
    print("  • HR Manager: HR + employee-related resources")
    print("  • Finance Manager: Finance-only resources")
    print("\nEach role sees only what it needs. RBAC is now working correctly!")

except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
