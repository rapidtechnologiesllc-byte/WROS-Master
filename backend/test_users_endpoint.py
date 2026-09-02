#!/usr/bin/env python3
"""
Debug script to test /hr/users/all endpoint
import logging
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users

db = SessionLocal()

try:
    print("Testing /hr/users/all endpoint debug...")

    # Test 1: Can we query users?
    print("\n1. Querying users...")
    users = db.query(Users).all()
    print(f"   [OK] Found {len(users)} users")

    if len(users) > 0:
        u = users[0]
        print(f"\n2. Testing first user: {u.UserEmail}")
        print(f"   - UserID: {u.UserID}")
        print(f"   - UserRole: {u.UserRole}")
        print(f"   - role_id: {u.role_id}")
        print(f"   - role relationship: {u.role}")

        # Test accessing properties
        print(f"   - role.name: {u.role.name if u.role else 'None'}")
        print(f"   - department: {u.department}")
        print(f"   - bu_context: {u.bu_context}")

        if u.department:
            print(f"   - department.name: {u.department.name}")
        if u.bu_context:
            print(f"   - bu_context.name: {u.bu_context.name}")

        print("\n[SUCCESS] All relationships accessible")

except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
