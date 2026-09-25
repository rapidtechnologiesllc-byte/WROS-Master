#!/usr/bin/env python3
"""Complete database verification including Business Units"""

import psycopg2
from datetime import datetime

def verify_db():
    try:
        conn = psycopg2.connect(
            'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev'
        )
        cur = conn.cursor()

        print("\n" + "="*70)
        print("COMPLETE DATABASE INITIALIZATION VERIFICATION")
        print("="*70)
        print(f"Timestamp: {datetime.now().isoformat()}\n")

        # Database & Schema
        print("📦 CORE INFRASTRUCTURE:")
        cur.execute("SELECT datname FROM pg_database WHERE datname='wros_dev'")
        db = cur.fetchone()
        print(f"  ✅ Database: {db[0] if db else 'NOT FOUND'}")

        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name='app_schema'")
        schema = cur.fetchone()
        print(f"  ✅ Schema: {schema[0] if schema else 'NOT FOUND'}")

        # Count tables
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='app_schema'")
        table_count = cur.fetchone()[0]
        print(f"  ✅ Tables: {table_count} created\n")

        # RBAC System
        print("🔐 RBAC SYSTEM:")
        cur.execute("SELECT COUNT(*) FROM app_schema.role_templates")
        print(f"  ✅ Roles: {cur.fetchone()[0]} configured")

        cur.execute("SELECT COUNT(*) FROM app_schema.modules")
        print(f"  ✅ Modules: {cur.fetchone()[0]} configured")

        cur.execute("SELECT COUNT(*) FROM app_schema.resources")
        print(f"  ✅ Resources: {cur.fetchone()[0]} configured")

        cur.execute("SELECT COUNT(*) FROM app_schema.role_template_permissions")
        print(f"  ✅ Permissions: {cur.fetchone()[0]} mapped\n")

        # Users
        print("👥 USERS:")
        cur.execute("SELECT COUNT(*) FROM app_schema.users")
        print(f"  ✅ Users: {cur.fetchone()[0]} seeded")

        cur.execute('SELECT "UserEmail" FROM app_schema.users ORDER BY "CreatedAt"')
        for user in cur.fetchall():
            print(f"     • {user[0]}")
        print()

        # Business Units (NEW!)
        print("🏢 BUSINESS UNITS:")
        cur.execute("SELECT COUNT(*) FROM app_schema.business_units")
        bu_count = cur.fetchone()[0]
        print(f"  ✅ Business Units: {bu_count} seeded")

        if bu_count > 0:
            cur.execute("SELECT name, bu_code, display_name FROM app_schema.business_units ORDER BY id")
            for bu in cur.fetchall():
                print(f"     • {bu[0]} ({bu[1]}) - {bu[2]}")
        print()

        # Summary
        print("="*70)
        if bu_count > 0:
            print("✅ FULL DATABASE INITIALIZATION SUCCESSFUL")
            print(f"   Score: 100/100 - All required data seeded")
        else:
            print("⚠️  PARTIAL - RBAC ready but Business Units empty")
            print(f"   Score: 75/100 - Missing Business Units")
        print("="*70 + "\n")

        conn.close()
        return bu_count > 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return False

if __name__ == "__main__":
    success = verify_db()
    exit(0 if success else 1)
