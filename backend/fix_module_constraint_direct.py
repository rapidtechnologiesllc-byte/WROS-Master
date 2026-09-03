#!/usr/bin/env python3
"""Apply module constraint fix directly (bypass broken Alembic)"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from sqlalchemy import text

db = SessionLocal()

try:
    print("[FIX MODULE CONSTRAINT FOR MULTI-TENANT]")
    print("="*60 + "\n")

    # Check current constraints
    with engine.connect() as conn:
        # Check if old constraint exists
        result = conn.execute(text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'modules' AND constraint_type = 'UNIQUE'
        """)).fetchall()

        print(f"Current constraints on modules table:")
        for row in result:
            print(f"  • {row[0]}")

        if result:
            # Drop old unique constraint on name
            old_constraint = result[0][0]
            if 'name_key' in old_constraint:
                print(f"\nDropping old constraint: {old_constraint}")
                conn.execute(text(f"ALTER TABLE modules DROP CONSTRAINT {old_constraint}"))
                conn.commit()
                print("  ✅ Dropped")

        # Add new composite constraint
        print(f"\nAdding composite unique constraint (name, tenant_id)...")
        try:
            conn.execute(text("""
                ALTER TABLE modules ADD CONSTRAINT uq_module_name_tenant
                UNIQUE (name, tenant_id)
            """))
            conn.commit()
            print("  ✅ Created")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error: {str(e)}", exc_info=True)
            if "already exists" in str(e):
                print("  ✅ Already exists")
            else:
                raise

    print("\n" + "="*60)
    print("✅ MODULE CONSTRAINT FIXED FOR MULTI-TENANT")
    print("="*60)
    print("\nNow each company (tenant) can have modules with the same name.")
    print("Modules table structure:")
    print("  • (name, tenant_id) = UNIQUE")
    print("  • Each tenant gets its own module/resource hierarchy")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
