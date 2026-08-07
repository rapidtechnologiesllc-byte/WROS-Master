#!/usr/bin/env python3
"""Create a superuser account with full permissions in WROS."""

import sqlite3
from datetime import datetime
import uuid
import hashlib

DB_PATH = "local_dev.sqlite3"
SUPERUSER_EMAIL = "superuser@blitzenx.com"
SUPERUSER_PASSWORD = "Superuser@2026!"

def hash_password(password: str) -> str:
    """Hash password using SHA-256 (common pattern)."""
    return hashlib.sha256(password.encode()).hexdigest()

def create_superuser():
    """Create superuser with CEO role and all permissions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create user
        user_id = str(uuid.uuid4())
        hashed_pw = hash_password(SUPERUSER_PASSWORD)

        cursor.execute("""
            INSERT INTO users (UserID, email, password_hash, first_name, last_name, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            SUPERUSER_EMAIL,
            hashed_pw,
            "Super",
            "User",
            1,
            datetime.utcnow().isoformat()
        ))

        # Get CEO role (Super User is CEO equivalent per WROS docs)
        cursor.execute("SELECT id FROM rbac_roles WHERE name = 'Super User' LIMIT 1")
        role_result = cursor.fetchone()

        if role_result:
            role_id = role_result[0]
            # Assign role to user
            cursor.execute("""
                INSERT INTO rbac_user_roles (user_id, role_id, assigned_at)
                VALUES (?, ?, ?)
            """, (user_id, role_id, datetime.utcnow().isoformat()))

            print(f"✅ Created superuser: {SUPERUSER_EMAIL}")
            print(f"   Password: {SUPERUSER_PASSWORD}")
            print(f"   User ID: {user_id}")
            print(f"   Role: Super User (CEO)")
        else:
            print("❌ Super User role not found in database")

        conn.commit()

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_superuser()
