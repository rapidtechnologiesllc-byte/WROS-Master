#!/usr/bin/env python3
"""
import logging
Phase 2 Database Migration - Candidate Isolation Implementation

Applies the candidate isolation schema changes to add BU locking capability.
Run this once after Phase 2 code is deployed.

Usage:
    python apply_phase2_migration.py

This script:
1. Adds submission_bu_id, associated_bu_id, submission_timestamp columns
2. Creates performance indexes
3. Verifies migration success
4. Reports results
"""

import sys
from sqlalchemy import text
from app.core.database import SessionLocal

def apply_migration():
    """Apply Phase 2 candidate isolation migration."""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("Phase 2 Migration: Candidate Isolation Implementation")
        print("=" * 80)

        # Step 1: Check if columns already exist (idempotent)
        print("\n[1/4] Checking if columns already exist...")
        result = db.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'candidates' AND COLUMN_NAME = 'submission_bu_id'
        """)).fetchone()

        if result:
            print("      ✅ Columns already exist - migration already applied")
            return True

        # Step 2: Add isolation columns
        print("[2/4] Adding candidate isolation columns...")
        db.execute(text("""
            ALTER TABLE candidates ADD COLUMN (
                submission_bu_id VARCHAR(36) REFERENCES business_units(id) ON DELETE SET NULL,
                associated_bu_id VARCHAR(36) REFERENCES business_units(id) ON DELETE SET NULL,
                submission_timestamp TIMESTAMP NULL DEFAULT NULL
            )
        """))
        print("      ✅ Columns added")

        # Step 3: Create performance indexes
        print("[3/4] Creating performance indexes...")
        db.execute(text("""
            CREATE INDEX idx_candidates_submission_bu ON candidates(submission_bu_id)
        """))
        db.execute(text("""
            CREATE INDEX idx_candidates_associated_bu ON candidates(associated_bu_id)
        """))
        db.execute(text("""
            CREATE INDEX idx_candidates_isolation_status ON candidates(associated_bu_id, submission_timestamp DESC)
        """))
        print("      ✅ Indexes created")

        # Step 4: Verify migration
        print("[4/4] Verifying migration...")
        result = db.execute(text("""
            SELECT
                COUNT(*) as total_candidates,
                COUNT(CASE WHEN associated_bu_id IS NULL THEN 1 END) as unassociated,
                COUNT(CASE WHEN associated_bu_id IS NOT NULL THEN 1 END) as associated
            FROM candidates
        """)).fetchone()

        total, unassociated, associated = result
        print(f"      ✅ Migration verified!")
        print(f"         Total candidates: {total}")
        print(f"         Unassociated: {unassociated} (visible to all HR)")
        print(f"         Associated: {associated} (locked to BU)")

        # Commit transaction
        db.commit()

        print("\n" + "=" * 80)
        print("✅ Migration completed successfully!")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Deploy Phase 2 code changes")
        print("2. Restart backend service")
        print("3. Test candidate submission to BU")
        print("4. Verify candidate isolation in queries")

        return True

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        print("Rolled back all changes")
        return False

    finally:
        db.close()

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
