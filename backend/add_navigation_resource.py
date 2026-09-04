#!/usr/bin/env python3
"""Add navigation resource to database"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.role_template import Resource, Module, RoleTemplate, RoleTemplatePermission
from app.models.tenant import Tenant

db = SessionLocal()

try:
    # Get the BlitzenX tenant
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()

    if not tenant:
        print("BlitzenX tenant not found")
        sys.exit(1)

    # Get or create System module
    system_module = db.query(Module).filter(
        Module.name == "System",
        Module.tenant_id == tenant.id
    ).first()

    if not system_module:
        system_module = Module(
            name="System",
            display_name="System",
            tenant_id=tenant.id,
            enabled=True
        )
        db.add(system_module)
        db.commit()
        print("[OK] Created System module")

    # Check if navigation resource already exists
    nav_resource = db.query(Resource).filter(
        Resource.name == "navigation",
        Resource.tenant_id == tenant.id
    ).first()

    if nav_resource:
        print("[OK] Navigation resource already exists")
    else:
        # Create navigation resource
        nav_resource = Resource(
            name="navigation",
            display_name="Navigation",
            module_id=system_module.id,
            tenant_id=tenant.id,
            description="Access to personalized navigation menu",
            enabled=True
        )
        db.add(nav_resource)
        db.commit()
        print("[OK] Created navigation resource")

        # Now grant it to Super User via permissions
        super_user = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Super User",
            RoleTemplate.tenant_id == tenant.id
        ).first()

        if super_user:
            # Check if permission already exists
            existing_perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == super_user.id,
                RoleTemplatePermission.resource_id == nav_resource.id
            ).first()

            if not existing_perm:
                perm = RoleTemplatePermission(
                    role_template_id=super_user.id,
                    resource_id=nav_resource.id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True
                )
                db.add(perm)
                db.commit()
                print("[OK] Granted navigation permission to Super User")
            else:
                print("[OK] Super User already has navigation permission")

    print("[SUCCESS] Navigation resource setup complete")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
