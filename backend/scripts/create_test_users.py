#!/usr/bin/env python3
"""
Create test users for all 4 role templates.
import logging
Useful for RBAC testing with different permission levels.

Usage:
  python scripts/create_test_users.py
"""

import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate
from app.core.security import get_password_hash
from app.core.logging import logger

TEST_USERS = [
    {
        "email": "super_user@test.com",
        "password": "SuperUser123!",
        "name": "Super User Test",
        "role": "Super User",
        "business_unit_id": 1,
    },
    {
        "email": "recruiter@test.com",
        "password": "Recruiter123!",
        "name": "Test Recruiter",
        "role": "Recruiter",
        "business_unit_id": 1,
    },
    {
        "email": "finance_mgr@test.com",
        "password": "FinanceMgr123!",
        "name": "Finance Manager Test",
        "role": "Finance Manager",
        "business_unit_id": 1,
    },
    {
        "email": "employee@test.com",
        "password": "Employee123!",
        "name": "Test Employee",
        "role": "Employee",
        "business_unit_id": 1,
    },
]

def create_test_users(db: Session):
    """Create test users for each role template."""

    tenant_id = 1
    created_count = 0

    for user_data in TEST_USERS:
        # Check if user already exists
        existing = db.query(Users).filter(
            Users.UserEmail == user_data["email"],
            Users.tenant_id == tenant_id
        ).first()

        if existing:
            logger.info(f"User already exists: {user_data['email']}")
            continue

        # Get role template
        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.name == user_data["role"],
            RoleTemplate.tenant_id == tenant_id
        ).first()

        if not role_template:
            logger.error(f"Role template not found: {user_data['role']}")
            continue

        try:
            # Create user with generated UserID
            user = Users(
                UserID=str(uuid.uuid4()),
                UserName=user_data["name"],
                UserEmail=user_data["email"],
                UserPassword=get_password_hash(user_data["password"]),
                UserRole=user_data["role"],  # Legacy role field
                role_template_id=role_template.id,  # New RBAC system - single role per user
                is_active=True,
                business_unit_id=user_data["business_unit_id"],
                tenant_id=tenant_id,
            )
            db.add(user)
            db.commit()

            logger.info(f"✓ Created user: {user_data['email']} with role {user_data['role']}")
            created_count += 1

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to create user {user_data['email']}: {e}")

            logger.info(f"\nCreated {created_count} test users")
    return created_count

if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_test_users(db)
    finally:
        db.close()
