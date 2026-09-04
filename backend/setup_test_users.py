#!/usr/bin/env python3
import logging
"""Create test users with correct passwords for local development."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import Users
from app.utils.uniq_id_generator import user_id_generator
from sqlalchemy import text

def setup_test_users():
    """Create test users if they don't exist."""
    db = SessionLocal()

    try:
        print("[SETUP] Creating test users...")

        # Test users: email -> password mapping
        test_users = {
            "am@blitzenx.com": "Am@123",
            "admin@blitzenx.com": "Admin@123",
            "cfotest@blitzenx.com": "CFO@123",
            "partnertest@blitzenx.com": "Partner@123",
        }

        created = 0
        for email, password in test_users.items():
            # Check if user exists
            result = db.query(Users).filter(Users.UserEmail == email).first()

            if result:
                print(f"  [SKIP] User {email} already exists")
                continue

            # Create new user
            user = Users(
                UserID=user_id_generator(),
                UserName=email.split("@")[0].title(),
                UserEmail=email,
                UserPassword=get_password_hash(password),
                UserRole="Employee",  # Default role
                tenant_id=1,
                mfa_enabled=False,
                digest_enabled=False,
                thunder_enabled=True,
                business_unit_id=1,  # NA business unit
            )

            db.add(user)
            db.commit()
            created += 1
            print(f"  [OK] Created user {email}")

        print(f"\n[SUMMARY] {created} test users created")

        # Now assign CEO, CFO, Partner roles
        print("\n[RBAC] Assigning roles...")

        role_assignments = {
            "am@blitzenx.com": "CEO",
            "admin@blitzenx.com": "CEO",
            "cfotest@blitzenx.com": "CFO",
            "partnertest@blitzenx.com": "Partner",
        }

        for email, role_name in role_assignments.items():
            # Get user
            user = db.query(Users).filter(Users.UserEmail == email).first()
            if not user:
                print(f"  [ERROR] User {email} not found")
                continue

            # Get role ID
            result = db.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name})
            role_id = result.scalar()

            if not role_id:
                print(f"  [ERROR] Role {role_name} not found")
                continue

            # Get business unit
            result = db.execute(text("SELECT id FROM business_units WHERE bu_code = 'NA' LIMIT 1"))
            bu_id = result.scalar()

            if not bu_id:
                # Create default business unit
                db.execute(
                    text("INSERT INTO business_units (name, bu_code, tenant_id, is_active) VALUES ('North America', 'NA', 1, 1)")
                )
                db.commit()
                result = db.execute(text("SELECT id FROM business_units WHERE bu_code = 'NA' LIMIT 1"))
                bu_id = result.scalar()

            # Check if assignment exists
            result = db.execute(
                text("SELECT id FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"),
                {"user_id": user.UserID, "role_id": role_id}
            )

            if result.scalar():
                print(f"  [SKIP] User {email} already has role {role_name}")
                continue

            # Assign role
            import uuid
            db.execute(
                text("INSERT INTO user_roles (id, user_id, role_id, business_unit_id) VALUES (:id, :user_id, :role_id, :bu_id)"),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user.UserID,
                    "role_id": role_id,
                    "bu_id": bu_id
                }
            )
            db.commit()
            print(f"  [OK] Assigned {role_name} role to {email}")

        print("\n[SUCCESS] Test user setup complete!")
        print("\nTest credentials:")
        print("  CEO: am@blitzenx.com / Am@123")
        print("  CEO: admin@blitzenx.com / Admin@123")
        print("  CFO: cfotest@blitzenx.com / CFO@123")
        print("  Partner: partnertest@blitzenx.com / Partner@123")

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
    setup_test_users()
