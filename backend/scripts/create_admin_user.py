#!/usr/bin/env python3
"""
Create a Super User admin account in production.
Run on production server via SSH.

Usage:
  python create_admin_user.py
  # Then enter email, name, and password when prompted
"""

import sys
import getpass
from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security_local import get_password_hash
from app.utils.uniq_id_generator import user_id_generator


def create_super_user():
    """Create a new Super User account with interactive prompts."""

    print("\n" + "="*60)
    print("CREATE PRODUCTION SUPER USER")
    print("="*60 + "\n")

    # Get user input
    email = input("Email address: ").strip().lower()
    if not email or "@" not in email:
        print("ERROR: Invalid email address")
        return False

    name = input("Full name: ").strip()
    if not name:
        print("ERROR: Name is required")
        return False

    password = getpass.getpass("Password (hidden): ")
    if not password or len(password) < 8:
        print("ERROR: Password must be at least 8 characters")
        return False

    password_confirm = getpass.getpass("Confirm password (hidden): ")
    if password != password_confirm:
        print("ERROR: Passwords do not match")
        return False

    # Verify confirmation
    print(f"\nCreating Super User:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Role: Super User (full access)")
    print()

    confirm = input("Proceed? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return False

    # Create user
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
    success = create_super_user()
    sys.exit(0 if success else 1)
