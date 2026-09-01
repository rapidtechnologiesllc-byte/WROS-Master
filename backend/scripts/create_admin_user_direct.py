#!/usr/bin/env python3
"""
Create a Super User admin account directly (non-interactive).

Usage:
  python create_admin_user_direct.py <email> <name> <password>

Example:
  python create_admin_user_direct.py admin@blitzenx.com Mukund "BlitzenX$123"
"""

import sys
from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security_local import get_password_hash
from app.utils.uniq_id_generator import user_id_generator


def create_super_user_direct(email, name, password):
    """Create a new Super User account directly."""

    print(f"\nCreating Super User:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Role: Super User (full access)")

    try:
        db = SessionLocal()

        # Check if user already exists
        existing = db.query(Users).filter(Users.UserEmail == email).first()
        if existing:
            print(f"ERROR: User with email {email} already exists")
            db.close()
            return False

        # Create new user
        user = Users(
            UserID=user_id_generator(),
            UserEmail=email,
            UserName=name,
            UserPassword=get_password_hash(password),
            UserRole="Super User",
            tenant_id=1
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print("\n" + "="*60)
        print("SUCCESS: Super User created")
        print("="*60)
        print(f"User ID: {user.UserID}")
        print(f"Email: {user.UserEmail}")
        print(f"Name: {user.UserName}")
        print(f"Role: {user.UserRole}")
        print(f"Created: {user.created_at}")
        print("="*60 + "\n")

        db.close()
        return True

    except Exception as e:
        print(f"\nERROR: Failed to create user: {str(e)}")
        try:
            db.rollback()
            db.close()
        except:
            pass
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_admin_user_direct.py <email> <name> <password>")
        print('Example: python create_admin_user_direct.py admin@blitzenx.com Mukund "BlitzenX$123"')
        sys.exit(1)

    email = sys.argv[1]
    name = sys.argv[2]
    password = sys.argv[3]

    success = create_super_user_direct(email, name, password)
    sys.exit(0 if success else 1)
