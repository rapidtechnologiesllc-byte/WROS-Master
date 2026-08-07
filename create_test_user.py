#!/usr/bin/env python3
"""Create test users in WROS."""

import sqlite3
import uuid
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.security import get_password_hash

DB_PATH = "local_dev.sqlite3"

def create_test_users():
    """Create test users with bcrypt-hashed passwords."""

    test_users = [
        {
            "email": "admin@blitzenx.com",
            "password": "Admin@123",
            "name": "Admin User",
            "role": "Admin"
        },
        {
            "email": "test@blitzenx.com",
            "password": "Test@123",
            "name": "Test User",
            "role": "HR Manager"
        },
        {
            "email": "superuser@blitzenx.com",
            "password": "Superuser!123",
            "name": "Super User",
            "role": "Super User"
        }
    ]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for user in test_users:
            email = user["email"]

            # Delete existing user
            cursor.execute("DELETE FROM users WHERE UserEmail = ?", (email,))
            print(f"Deleted existing user: {email}")

            # Create new user with bcrypt-hashed password
            user_id = str(uuid.uuid4())
            hashed_password = get_password_hash(user["password"])
            created_at = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT INTO users
                (UserID, UserEmail, UserPassword, UserName, UserRole, CreatedAt, mfa_enabled, digest_enabled, thunder_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                email,
                hashed_password,
                user["name"],
                user["role"],
                created_at,
                0,
                0,
                0
            ))

            print(f"[OK] Created user: {email}")
            print(f"  Name: {user['name']}")
            print(f"  Role: {user['role']}")
            print(f"  Password: {user['password']}")
            print()

        conn.commit()
        print("[OK] All users created successfully!")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_users()
