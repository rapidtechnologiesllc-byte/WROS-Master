"""
Clean up old/fake modules and resources from database.
Keep only the modules defined in init_resources.py
"""
from app.core.database import SessionLocal
import logging
from app.models.role_template import Module, Resource

# List of valid modules from init_resources.py
VALID_MODULES = {
    "Personal", "Recruitment", "Workforce", "Sales", "Project Management",
    "Finance", "Reporting", "System", "Executive", "Admin", "AI & Automation"
}

def cleanup_old_resources(db, tenant_id=1):
    """Delete modules and resources not in VALID_MODULES"""

    print("Identifying old/fake modules to delete...")

    # Get all modules
    all_modules = db.query(Module).filter(Module.tenant_id == tenant_id).all()

    deleted_modules = 0
    deleted_resources = 0

    for module in all_modules:
        if module.name not in VALID_MODULES:
            print(f"  [DELETE] Deleting module: {module.name}")

            # Delete all resources in this module first
            resources = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.tenant_id == tenant_id
            ).all()

            for resource in resources:
                db.delete(resource)
                deleted_resources += 1

            # Delete the module
            db.delete(module)
            deleted_modules += 1

    db.commit()

    print(f"\nCleanup Complete:")
    print(f"  Deleted modules: {deleted_modules}")
    print(f"  Deleted resources: {deleted_resources}")
    print(f"  Remaining modules: {len(VALID_MODULES)}")

    return deleted_modules, deleted_resources

def verify_modules(db, tenant_id=1):
    """Verify only valid modules remain"""
    print("\nVerifying remaining modules...")

    all_modules = db.query(Module).filter(Module.tenant_id == tenant_id).all()
    module_names = {m.name for m in all_modules}

    for module_name in VALID_MODULES:
        if module_name in module_names:
            print(f"  [OK] {module_name}")
        else:
            print(f"  [MISSING] {module_name}")

    print(f"\nTotal modules in database: {len(all_modules)}")
    print(f"Expected modules: {len(VALID_MODULES)}")

    if len(all_modules) > len(VALID_MODULES):
        print("\nWARNING: Still have extra modules!")
        for module in all_modules:
            if module.name not in VALID_MODULES:
                print(f"  - {module.name}")

def main():
    db = SessionLocal()
    try:
        print("="*70)
        print("DATABASE CLEANUP: Remove old/fake modules and resources")
        print("="*70)

        # Step 1: Cleanup
        deleted_modules, deleted_resources = cleanup_old_resources(db, tenant_id=1)

        # Step 2: Verify
        verify_modules(db, tenant_id=1)

        print("\n" + "="*70)
        print("SUCCESS: Database cleaned up!")
        print("="*70)
        print("\nNext step: Run init_resources.py to re-seed all modules")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"ERROR: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
