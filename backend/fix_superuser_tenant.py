#!/usr/bin/env python3
"""Move SuperUser to correct tenant (1) where resources exist"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate

db = SessionLocal()

try:
    # Find SuperUser account
    user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()

    if not user:
        print("SuperUser not found")
        sys.exit(1)

    print(f"Found SuperUser in tenant {user.tenant_id}")

    if user.tenant_id != 1:
        # Find Super User role in tenant 1
        role = db.query(RoleTemplate).filter(
            RoleTemplate.name == "Super User",
            RoleTemplate.tenant_id == 1
        ).first()

        if not role:
            print("Super User role not found in tenant 1")
            sys.exit(1)

        # Move SuperUser to tenant 1
        user.tenant_id = 1
        user.role_template_id = role.id
        db.commit()

        print("✅ Moved SuperUser to tenant 1 (default)")
        print(f"   Now has access to all {171} resources in tenant 1")
    else:
        print("✅ SuperUser is already in correct tenant")

except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
