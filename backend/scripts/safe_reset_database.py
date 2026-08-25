"""
Safe Database Reset Script

This script will ONLY reset LOCAL development databases.
REFUSES to touch production databases for safety.

Usage:
    python scripts/safe_reset_database.py

Environment Requirements:
    - DATABASE_URL must point to localhost/127.0.0.1
    - ENVIRONMENT must NOT be "production"
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database_safety import (
    is_production_database,
    is_local_database,
    get_environment,
    ProductionDatabaseError
)


def parse_db_url(db_url: str) -> dict:
    """Parse PostgreSQL connection string."""
    parsed = urlparse(db_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
    }


def reset_database():
    """Reset local development database safely."""
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)

    # Safety Check 1: Refuse production databases
    if is_production_database(db_url):
        print("\n" + "=" * 80)
        print("🚨 PRODUCTION DATABASE DETECTED - RESET REFUSED")
        print("=" * 80)
        print(f"\nDatabase URL: {db_url}")
        print(f"Environment: {get_environment()}")
        print("\nYOU CANNOT RESET PRODUCTION DATABASES LOCALLY!")
        print("\nIf you need to reset production:")
        print("1. SSH to production server only")
        print("2. Contact DevOps team")
        print("3. Never reset prod from local machine")
        print("=" * 80 + "\n")
        sys.exit(1)

    # Safety Check 2: Verify it's a local database
    if not is_local_database(db_url):
        print("\n⚠️  WARNING: Database doesn't look like local development:")
        print(f"   {db_url}")
        response = input("\nAre you SURE this is a local development database? (yes/no): ")
        if response.lower() != "yes":
            print("Reset cancelled.")
            sys.exit(0)

    # Parse connection details
    db_config = parse_db_url(db_url)
    print(f"\n✓ Local database confirmed: {db_config['database']} @ {db_config['host']}")

    # Confirm reset
    print(f"\n⚠️  This will DELETE ALL DATA from: {db_config['database']}")
    response = input(f"Type 'reset {db_config['database']}' to confirm: ")

    if response != f"reset {db_config['database']}":
        print("Reset cancelled.")
        sys.exit(0)

    # Connect and reset
    try:
        print(f"\n🔄 Connecting to database...")
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database='postgres'  # Connect to postgres DB to drop/recreate
        )
        cur = conn.cursor()

        # Terminate connections to target database
        target_db = db_config['database']
        print(f"🔄 Terminating connections to {target_db}...")
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{target_db}'
            AND pid <> pg_backend_pid();
        """)

        # Drop and recreate database
        print(f"🔄 Dropping {target_db}...")
        cur.execute(f"DROP DATABASE IF EXISTS {target_db};")

        print(f"🔄 Creating {target_db}...")
        cur.execute(f"CREATE DATABASE {target_db} OWNER {db_config['user']};")

        conn.commit()
        print(f"\n✅ SUCCESS! Database reset complete: {target_db}")
        print(f"   Ready for fresh schema initialization")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    reset_database()
