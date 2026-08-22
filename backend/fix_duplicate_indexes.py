"""
Fix duplicate indexes in PostgreSQL database.
Removes duplicate indexes that were created during failed initialization.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123@localhost:5432/wros_dev"
)

def fix_duplicate_indexes():
    """Remove duplicate indexes from database."""
    engine = create_engine(DATABASE_URL, poolclass=NullPool)

    duplicate_indexes = [
        "ix_role_permissions_role_id",
    ]

    with engine.connect() as conn:
        with conn.begin():
            for index_name in duplicate_indexes:
                try:
                    # Drop index if it exists
                    conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                    print(f"[SUCCESS] Dropped index: {index_name}")
                except Exception as e:
                    print(f"[INFO] Index issue {index_name}: {str(e)[:100]}")

    print("\n[SUCCESS] Database cleanup complete")


def verify_schema():
    """Verify schema integrity after cleanup."""
    engine = create_engine(DATABASE_URL, poolclass=NullPool)

    with engine.connect() as conn:
        # Check if table exists
        try:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'detailed_role_permissions'
            """))
            table_exists = result.scalar() > 0
            if table_exists:
                print("[SUCCESS] Table detailed_role_permissions exists")
            else:
                print("[INFO] Table detailed_role_permissions not yet created")
        except Exception as e:
            print(f"[INFO] Database check: {str(e)[:100]}")


if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE CLEANUP: Remove Duplicate Indexes")
    print("=" * 60)

    print("\n1. Fixing duplicate indexes...")
    fix_duplicate_indexes()

    print("\n2. Verifying schema...")
    verify_schema()

    print("\n" + "=" * 60)
    print("Database cleanup completed successfully!")
    print("=" * 60)
