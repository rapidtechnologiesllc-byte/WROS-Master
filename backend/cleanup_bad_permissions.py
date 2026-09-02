#!/usr/bin/env python3
"""Remove the bad 'all-to-all' permissions"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.role_template import RoleTemplatePermission

db = SessionLocal()
try:
    count = db.query(RoleTemplatePermission).count()
    print(f"Removing {count} permissions...")
    db.query(RoleTemplatePermission).delete()
    db.commit()
    print(f"✅ Removed all {count} permissions")
    print("   Ready for proper role-specific permissions")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
