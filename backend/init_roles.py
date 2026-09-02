#!/usr/bin/env python3
import logging
"""Initialize WROS database with default RBAC roles."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from datetime import datetime

def init_roles():
    """Create default roles if they don't exist."""

    db = SessionLocal()

    try:
        # Check if roles already exist
        existing_roles = db.query(Role).count()
        if existing_roles > 0:
            print(f"[OK] {existing_roles} roles already exist in database")
            return

        # Create default roles
        default_roles = [
            {
                "name": "Super User",
                "description": "Full system access - can manage all features, users, and configuration"
            },
            {
                "name": "Admin",
                "description": "Administrative access - can manage users, roles, and most system features"
            },
            {
                "name": "HR Manager",
                "description": "HR management - can manage candidates, interviews, and employee data"
            },
            {
                "name": "Recruiter",
                "description": "Recruitment - can search, screen, and manage candidates"
            },
            {
                "name": "Finance",
                "description": "Finance access - can manage invoices, expenses, and financial reports"
            },
            {
                "name": "Manager",
                "description": "Manager - can manage teams and view reports"
            },
            {
                "name": "Employee",
                "description": "Employee - can view own data and submit timesheets"
            },
        ]

        print("[INIT] Creating default roles...")
        for role_data in default_roles:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                created_at=datetime.utcnow()
            )
            db.add(role)
            print(f"  [OK] Created role: {role_data['name']}")

        db.commit()
        print(f"\n[SUCCESS] {len(default_roles)} roles created successfully!")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_roles()
