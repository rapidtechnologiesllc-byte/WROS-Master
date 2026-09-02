#!/usr/bin/env python3
import logging
"""Add missing business_unit_id column to bu_revenue_targets table."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("\n" + "=" * 70)
print("ADDING business_unit_id COLUMN TO bu_revenue_targets")
print("=" * 70)

try:
    # Check if column already exists
    result = db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'bu_revenue_targets' AND column_name = 'business_unit_id'
    """))

    if result.fetchone():
        print("\n[INFO] Column 'business_unit_id' already exists")
    else:
        print("\n[ACTION] Adding 'business_unit_id' column...")
        db.execute(text("""
            ALTER TABLE bu_revenue_targets ADD COLUMN business_unit_id INTEGER;
        """))
        print("    [OK] Column added")

        # Add FK constraint after making it nullable
        print("\n[ACTION] Adding foreign key constraint...")
        db.execute(text("""
            ALTER TABLE bu_revenue_targets
            ADD CONSTRAINT fk_bu_revenue_targets_business_unit_id
            FOREIGN KEY (business_unit_id) REFERENCES business_units(id);
        """))
        print("    [OK] FK constraint added")

        # Make column NOT NULL after ensuring migration is done
        print("\n[ACTION] Making column NOT NULL...")
        db.execute(text("""
            UPDATE bu_revenue_targets SET business_unit_id = 1 WHERE business_unit_id IS NULL;
            ALTER TABLE bu_revenue_targets ALTER COLUMN business_unit_id SET NOT NULL;
        """))
        print("    [OK] Column set to NOT NULL")

    # Make bu_context_id optional (nullable) since it's not always used
    print("\n[ACTION] Making bu_context_id optional...")
    db.execute(text("""
        ALTER TABLE bu_revenue_targets ALTER COLUMN bu_context_id DROP NOT NULL;
    """))
    print("    [OK] bu_context_id is now nullable")

    db.commit()
    print("\n[SUCCESS] Migration completed successfully")

except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    db.rollback()
    print(f"\n[ERROR] Migration failed:")
    print(f"    {type(e).__name__}: {str(e)}")
    sys.exit(1)
finally:
    db.close()

print("\n" + "=" * 70)
print("Schema updated. BU Revenue Targets endpoint should now work.")
print("=" * 70 + "\n")
