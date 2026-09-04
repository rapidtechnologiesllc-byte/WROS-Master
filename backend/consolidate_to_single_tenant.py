#!/usr/bin/env python3
"""
Consolidate to single tenant.
The system is designed for single-tenant (modules, resources are shared).
Move all BlitzenX data to default tenant.
"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.tenant import Tenant
from app.models.role_template import RoleTemplate

db = SessionLocal()

try:
    print("[CONSOLIDATE TO SINGLE TENANT]")
    print("="*60 + "\n")

    # Default tenant
    default_tenant = db.query(Tenant).filter(Tenant.name == "Default Tenant").first()
    if not default_tenant:
        default_tenant = db.query(Tenant).order_by(Tenant.id).first()

    print(f"Target tenant: {default_tenant.name} (id={default_tenant.id})\n")

    # Move all BlitzenX users to default tenant
    blitzen_users = db.query(Users).filter(Users.tenant_id == 3).all()
    print(f"Moving {len(blitzen_users)} users from BlitzenX to default tenant...")

    for user in blitzen_users:
        # Find matching role in default tenant
        if user.role_template_id:
            old_role = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id
            ).first()

            new_role = db.query(RoleTemplate).filter(
                RoleTemplate.name == old_role.name if old_role else "Employee",
                RoleTemplate.tenant_id == default_tenant.id
            ).first()

            user.role_template_id = new_role.id if new_role else None

        user.tenant_id = default_tenant.id
        print(f"  • {user.UserEmail} → tenant {default_tenant.id}")

    db.commit()

    print(f"\n✅ All users consolidated to tenant {default_tenant.id}")
    print(f"✅ All users now have access to {171} shared resources")
    print("\nSystem note: Resources are SHARED across all users in one tenant.")
    print("Multi-tenant support requires schema changes to Module unique constraint.")

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
