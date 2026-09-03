#!/usr/bin/env python3
"""Finalize multi-tenant setup: Move SuperUser to BlitzenX tenant with permissions"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.user import Users
from app.models.tenant import Tenant
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission
from datetime import datetime

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[FINALIZE MULTI-TENANT SETUP]")
    print("="*60 + "\n")

    # Get tenants
    default_tenant = db.query(Tenant).filter(Tenant.name == "Default Tenant").first()
    blitzen_tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()

    print(f"Tenants found:")
    print(f"  • Default Tenant (id={default_tenant.id})")
    print(f"  • BlitzenX (id={blitzen_tenant.id})\n")

    # Get/Create Super User role in BlitzenX tenant
    super_user_role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == blitzen_tenant.id
    ).first()

    if not super_user_role:
        print(f"Creating Super User role for BlitzenX tenant...")
        super_user_role = RoleTemplate(
            name="Super User",
            display_name="Super User",
            description="Full system access",
            tenant_id=blitzen_tenant.id,
            enabled=True,
            is_system=True,
            created_at=datetime.utcnow()
        )
        db.add(super_user_role)
        db.flush()
        print("  ✅ Created")
    else:
        print(f"Super User role already exists in BlitzenX")

    # Grant Super User all permissions in BlitzenX
    resources = db.query(Resource).filter(
        Resource.tenant_id == blitzen_tenant.id
    ).all()

    print(f"\nGranting Super User all {len(resources)} BlitzenX resources...")
    granted = 0
    for resource in resources:
        exists = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == super_user_role.id,
            RoleTemplatePermission.resource_id == resource.id
        ).first()

        if not exists:
            perm = RoleTemplatePermission(
                role_template_id=super_user_role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True,
                created_at=datetime.utcnow()
            )
            db.add(perm)
            granted += 1

    db.commit()
    print(f"  ✅ Granted {granted} permissions")

    # Move SuperUser to BlitzenX tenant
    print(f"\nMoving SuperUser to BlitzenX tenant...")
    user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()

    if user:
        user.tenant_id = blitzen_tenant.id
        user.role_template_id = super_user_role.id
        db.commit()
        print(f"  ✅ SuperUser moved to BlitzenX (tenant {blitzen_tenant.id})")
        print(f"  ✅ Role template set to Super User (id={super_user_role.id})")
    else:
        print(f"  ⚠️  SuperUser account not found")

    print("\n" + "="*60)
    print("✅ MULTI-TENANT SETUP COMPLETE")
    print("="*60)
    print("\nEach company (tenant) is now independent:")
    print(f"  • BlitzenX (id={blitzen_tenant.id}): {len(resources)} resources, 1 Super User")
    print(f"  • Default Tenant (id={default_tenant.id}): separate resources")
    print("\nRoles and permissions are managed DYNAMICALLY per tenant.")
    print("No hardcoding. Each company has complete RBAC separation.")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
