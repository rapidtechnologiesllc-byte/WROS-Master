"""
Direct script to create SLMDecision table in database.
Run this when Alembic migrations are having issues.
"""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.slm_decision import SLMDecision
from sqlalchemy import text

def create_slm_table():
    """Create SLMDecision table directly."""
    db = SessionLocal()

    try:
        # Check if table already exists
        result = db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'slm_decisions'
            )
        """))

        table_exists = result.scalar()

        if table_exists:
            print("✓ SLMDecision table already exists")
            return True

        # Create the table using SQLAlchemy metadata
        print("Creating SLMDecision table...")
        SLMDecision.metadata.create_all(bind=db.get_bind())

        # Verify creation
        result = db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'slm_decisions'
            )
        """))

        if result.scalar():
            print("✓ SLMDecision table created successfully")

            # Verify columns
            columns_result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'slm_decisions'
                ORDER BY ordinal_position
            """))

            columns = [row[0] for row in columns_result]
            print(f"\nColumns created ({len(columns)}):")
            for col in columns:
                print(f"  - {col}")

            return True
        else:
            print("✗ Failed to create SLMDecision table")
            return False

    except Exception as e:
        print(f"✗ Error creating table: {e}")
        return False
    finally:
        db.close()

if __name__ == '__main__':
    success = create_slm_table()
    sys.exit(0 if success else 1)
