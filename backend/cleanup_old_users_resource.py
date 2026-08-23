#!/usr/bin/env python3
"""Delete the old 'users' resource from the database and keep only 'users-access-control'."""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.role_template import Resource

def cleanup_old_users_resource(db: Session, tenant_id: int = 1):
    """Delete old 'users' resource, keep 'users-access-control'."""

    print("Cleaning up old 'users' resource...")

    # Find and delete the old "users" resource
    old_users = db.query(Resource).filter(
        Resource.name == "users",
        Resource.tenant_id == tenant_id,
        Resource.enabled == True
    ).first()

    if old_users:
        print(f"  Found old 'users' resource (id={old_users.id})")
        print(f"  Route: {old_users.route_path}")

        # Delete it
        db.delete(old_users)
        db.commit()
        print(f"  DELETED: old 'users' resource removed from database")
    else:
        print("  OK: old 'users' resource not found (already deleted)")

    # Verify new one exists
    new_users_ac = db.query(Resource).filter(
        Resource.name == "users_access_control",
        Resource.tenant_id == tenant_id
    ).first()

    if new_users_ac:
        print(f"  OK: 'users-access-control' resource found (id={new_users_ac.id})")
        print(f"  Route: {new_users_ac.route_path}")
    else:
        print("  ERROR: 'users-access-control' resource NOT found!")
        print("  Please run: python -m app.seeds.init_resources")
        return False

    print("\nCleanup complete!")
    print("Result: Old 'users' removed, only 'users-access-control' remains")
    return True

if __name__ == "__main__":
    db = SessionLocal()
    try:
        success = cleanup_old_users_resource(db, tenant_id=1)
        if success:
            print("\n" + "="*70)
            print("SUCCESS: Database cleaned!")
            print("="*70)
            print("\nRefresh your browser and the 'Users' item should be GONE")
            print("Only 'Users & Access Control' should appear in Admin menu")
        else:
            print("\nERROR: Cleanup failed. See above for details.")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()
