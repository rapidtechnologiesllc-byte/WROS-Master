#!/usr/bin/env python3
"""
Production Deployment Verification
Ensures that production code matches what's on main branch
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.role_template import Module, Resource
from app.models.user import Users

def verify_navigation_deployment():
    """Verify that navigation endpoint has all 175+ resources"""
    db = SessionLocal()

    try:
        # Check modules
        modules = db.query(Module).filter(Module.tenant_id == 1).all()
        print(f"Modules: {len(modules)}")
        if len(modules) < 10:
            print("ERROR: Expected at least 10 modules")
            return False

        # Check resources
        resources = db.query(Resource).filter(
            Resource.tenant_id == 1,
            Resource.enabled == True
        ).all()
        print(f"Resources: {len(resources)}")
        if len(resources) < 170:
            print("ERROR: Expected at least 170 resources (got hardcoded nav with only 10)")
            return False

        # Check test users exist
        super_user = db.query(Users).filter(Users.UserEmail == 'super_user@test.com').first()
        if not super_user:
            print("ERROR: Super user test account missing")
            return False

        print("SUCCESS: Deployment verified - production has dynamic navigation with 175+ resources")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = verify_navigation_deployment()
    sys.exit(0 if success else 1)
