#!/usr/bin/env python
"""Create a single super user in the database."""
import bcrypt
from app.core.database import SessionLocal
from app.models.user import Users

def create_superuser():
    """Create a super user."""
    db = SessionLocal()

    # Hash password
    password = "Admin@123"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Create user
    user = Users(
        UserID="superuser-001",
        UserName="Super Admin",
        UserEmail="admin@test.com",
        UserPassword=hashed,
        UserRole="Super Admin",
        tenant_id=1,
        mfa_enabled=False
    )

    db.add(user)
    db.commit()
    db.close()

    print("[OK] Super user created:")
    print("  Email: admin@test.com")
    print("  Password: Admin@123")
    print("  Role: Super Admin")

if __name__ == "__main__":
    create_superuser()
