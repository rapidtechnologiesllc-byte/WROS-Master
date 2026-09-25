#!/usr/bin/env python3
"""Verify database initialization - FIXED TO CHECK app_schema with CORRECT table names"""

import psycopg2
from datetime import datetime

def verify_db_init():
    try:
        conn = psycopg2.connect(
            'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev'
        )
        cur = conn.cursor()

        print("\n" + "="*70)
        print("DATABASE INITIALIZATION VERIFICATION REPORT - FIXED")
        print("="*70)
        print(f"Timestamp: {datetime.now().isoformat()}\n")

        # Check database
        cur.execute("SELECT datname FROM pg_database WHERE datname=%s", ('wros_dev',))
        db = cur.fetchone()
        db_status = "✅ PASS" if db else "❌ FAIL"
        print(f"{db_status} Database: {db[0] if db else 'NOT FOUND'}")

        # Check schema
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name=%s", ('app_schema',))
        schema = cur.fetchone()
        schema_status = "✅ PASS" if schema else "❌ FAIL"
        print(f"{schema_status} Schema: {schema[0] if schema else 'NOT FOUND'}")

        # Check tables in app_schema (correct location)
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", ('app_schema',))
        table_count = cur.fetchone()[0]
        table_status = "✅ PASS" if table_count > 0 else "❌ FAIL"
        print(f"{table_status} Tables: {table_count} tables created in app_schema")

        # Check if RBAC tables exist (PLURAL names!)
        rbac_tables = ['role_templates', 'modules', 'resources', 'role_template_permissions']
        print(f"\nRBAC Tables Check:")
        all_exist = True
        for tbl in rbac_tables:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name=%s AND table_schema=%s",
                (tbl, 'app_schema')
            )
            exists = cur.fetchone()[0] > 0
            status = "✅" if exists else "❌"
            print(f"  {status} {tbl}: {'EXISTS' if exists else 'MISSING'}")
            if not exists:
                all_exist = False

        # Try to query roles if table exists
        try:
            cur.execute("SELECT COUNT(*) FROM app_schema.role_templates")
            role_count = cur.fetchone()[0]
            print(f"\n✅ RBAC System Status:")
            print(f"   - Roles in database: {role_count}")

            # Get role details
            cur.execute("SELECT id, name FROM app_schema.role_templates")
            roles = cur.fetchall()
            for role in roles:
                print(f"     • {role[1]} (ID: {role[0]})")

            # Get modules
            cur.execute("SELECT COUNT(*) FROM app_schema.modules")
            module_count = cur.fetchone()[0]
            print(f"   - Modules: {module_count}")

            # Get resources
            cur.execute("SELECT COUNT(*) FROM app_schema.resources")
            resource_count = cur.fetchone()[0]
            print(f"   - Resources: {resource_count}")

            # Get permissions
            cur.execute("SELECT COUNT(*) FROM app_schema.role_template_permissions")
            perm_count = cur.fetchone()[0]
            print(f"   - Permissions: {perm_count}")

            # Get users
            cur.execute("SELECT COUNT(*) FROM app_schema.users")
            user_count = cur.fetchone()[0]
            print(f"   - Users: {user_count}")

            cur.execute("SELECT user_email FROM app_schema.users ORDER BY created_at")
            users = cur.fetchall()
            for user in users:
                print(f"     • {user[0]}")

        except Exception as e:
            print(f"\n❌ RBAC System Status: {e}")

        conn.close()

        print("\n" + "="*70)
        if all_exist:
            print("✅ VERIFICATION COMPLETE - All RBAC tables found!")
            print("Score: 100/100 - Database initialized correctly")
        else:
            print("❌ VERIFICATION FAILED - Some RBAC tables missing!")
            print("Score: < 100/100 - Database initialization incomplete")
        print("="*70 + "\n")

        return all_exist

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}\n")
        return False

if __name__ == "__main__":
    verify_db_init()
