"""
import logging
Migration: Switch from multi-role (user_roles) to single-role with custom overrides

Schema changes:
1. Populate users.role_id from user_roles (take first role if multiple)
2. Create user_custom_permissions table for permission overrides
3. Mark user_roles as deprecated (keep for audit, don't use)
"""

import psycopg2
from datetime import datetime

def migrate():
    conn = psycopg2.connect(
        host="localhost", port=5432, user="app_user",
        password="P7kQmR9xL2wJnV5sT8pM", database="onboarding_prod"
    )
    conn.set_isolation_level(0)
    c = conn.cursor()
    c.execute("SET search_path TO app_schema")

    print("MIGRATION: Single Role + Custom Overrides")
    print("=" * 70)

    # Step 1: Create user_custom_permissions table
    print("\n1. Creating user_custom_permissions table...")
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_custom_permissions (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES "users"("UserID"),
        resource_id INTEGER NOT NULL REFERENCES resources(id),
        can_view BOOLEAN DEFAULT FALSE,
        can_create BOOLEAN DEFAULT FALSE,
        can_edit BOOLEAN DEFAULT FALSE,
        can_delete BOOLEAN DEFAULT FALSE,
        override_reason VARCHAR(255),
        created_by VARCHAR(36),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, resource_id)
    )
    """)
    print("   [OK] Table created")

    # Step 2: Populate users.role_id from user_roles (take first/only role)
    print("\n2. Migrating users to single role_id...")
    c.execute("""
    UPDATE "users" u
    SET role_id = (
        SELECT role_template_id
        FROM user_roles ur
        WHERE ur.user_id = u."UserID"
        ORDER BY ur.created_at ASC
        LIMIT 1
    )
    WHERE role_id IS NULL
    AND "UserID" IN (SELECT DISTINCT user_id FROM user_roles)
    """)

    migrated = c.rowcount
    print(f"   [OK] Migrated {migrated} users")

    # Step 3: Log users with multiple roles (manual review needed)
    print("\n3. Checking for users with multiple roles...")
    c.execute("""
    SELECT user_id, COUNT(*) as role_count
    FROM user_roles
    GROUP BY user_id
    HAVING COUNT(*) > 1
    """)

    multi_role_users = c.fetchall()
    if multi_role_users:
        print(f"   WARNING: {len(multi_role_users)} users have multiple roles (kept first):")
        for user_id, count in multi_role_users:
            print(f"     - {user_id}: {count} roles -> kept 1st, others ignored")
    else:
        print("   [OK] No users with multiple roles")

    # Step 4: Verify migration
    print("\n4. Verification...")
    c.execute("""
    SELECT COUNT(*) FROM "users" WHERE role_id IS NOT NULL
    """)
    users_with_role = c.fetchone()[0]

    c.execute("""
    SELECT COUNT(*) FROM "users"
    """)
    total_users = c.fetchone()[0]

    print(f"   Users with role_id: {users_with_role}/{total_users}")

    # Step 5: Show migration summary
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print("\nNEW ARCHITECTURE (Option C):")
    print("  1. users.role_id -> role_template (SINGLE role per user)")
    print("  2. user_custom_permissions (override specific permissions)")
    print("  3. user_roles table (DEPRECATED - for audit trail only)")
    print("\nPERMISSION LOGIC:")
    print("  1. Get user's role_id")
    print("  2. Load role_template permissions")
    print("  3. Apply custom overrides from user_custom_permissions")
    print("  4. Result = base permissions + overrides")
    print("\nNo UNION logic, no multi-role complexity.")
    print("=" * 70)

    conn.close()

if __name__ == "__main__":
    migrate()
