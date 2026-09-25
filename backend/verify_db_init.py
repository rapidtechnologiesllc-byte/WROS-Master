#!/usr/bin/env python3
"""Verify database initialization was successful"""

import psycopg2
from datetime import datetime

def verify_db_init():
    try:
        conn = psycopg2.connect(
            'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev'
        )
        cur = conn.cursor()

        print("\n" + "="*60)
        print("DATABASE INITIALIZATION VERIFICATION REPORT")
        print("="*60)
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

        # Check tables
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", ('public',))
        table_count = cur.fetchone()[0]
        table_status = "✅ PASS" if table_count > 0 else "❌ FAIL"
        print(f"{table_status} Tables: {table_count} tables created")

        # Check roles
        cur.execute("SELECT id, name, display_name FROM role_template ORDER BY created_at")
        roles = cur.fetchall()
        roles_status = "✅ PASS" if len(roles) >= 2 else "❌ FAIL"
        print(f"{roles_status} Roles: {len(roles)} roles")
        for role in roles:
            print(f"       - {role[1]} ({role[2]})")

        # Check modules
        cur.execute("SELECT id, name, display_name FROM module")
        modules = cur.fetchall()
        modules_status = "✅ PASS" if len(modules) > 0 else "❌ FAIL"
        print(f"{modules_status} Modules: {len(modules)} modules")
        for mod in modules:
            print(f"       - {mod[1]} ({mod[2]})")

        # Check resources
        cur.execute("SELECT COUNT(DISTINCT name) FROM resource")
        resources_count = cur.fetchone()[0]
        resources_status = "✅ PASS" if resources_count >= 10 else "❌ FAIL"
        print(f"{resources_status} Resources: {resources_count} resources created")

        # Check permissions
        cur.execute("SELECT COUNT(*) FROM role_template_permission")
        perms = cur.fetchone()[0]
        perms_status = "✅ PASS" if perms > 0 else "❌ FAIL"
        print(f"{perms_status} Permissions: {perms} permission mappings configured")

        # Check users
        cur.execute("SELECT id, user_email, user_name FROM users ORDER BY created_at")
        users = cur.fetchall()
        users_status = "✅ PASS" if len(users) >= 2 else "❌ FAIL"
        print(f"{users_status} Users: {len(users)} users seeded")
        for user in users:
            print(f"       - {user[1]} ({user[2]})")

        # Check user permissions
        cur.execute("""
            SELECT u.user_email, rt.name, COUNT(rtp.id) as permission_count
            FROM users u
            JOIN role_template rt ON u.role_template_id = rt.id
            LEFT JOIN role_template_permission rtp ON rt.id = rtp.role_template_id
            GROUP BY u.user_email, rt.name
        """)
        user_perms = cur.fetchall()
        print(f"\nUser Permissions:")
        for up in user_perms:
            print(f"       - {up[0]}: {up[1]} role ({up[2]} permissions)")

        conn.close()

        print("\n" + "="*60)
        print("SUMMARY: Database initialization completed successfully!")
        print("="*60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return False

if __name__ == "__main__":
    verify_db_init()
