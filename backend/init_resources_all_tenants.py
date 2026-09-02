#!/usr/bin/env python3
"""
Initialize resources for ALL tenants (companies).
Each tenant gets its own complete module/resource structure.
"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.role_template import Module, Resource
from app.models.tenant import Tenant
from app.contracts import MODULES_AND_RESOURCES

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[INITIALIZE RESOURCES FOR ALL TENANTS]")
    print("="*60 + "\n")

    # Get all tenants
    tenants = db.query(Tenant).all()
    print(f"Found {len(tenants)} tenant(s) (companies)\n")

    for tenant in tenants:
        print(f"Processing tenant: {tenant.name} (id={tenant.id})")

        # For each module in the contract
        for module_name, resource_names in MODULES_AND_RESOURCES.items():
            # Check if module exists for this tenant
            module = db.query(Module).filter(
                Module.name == module_name,
                Module.tenant_id == tenant.id
            ).first()

            if not module:
                # Create module for this tenant
                module = Module(
                    name=module_name,
                    display_name=module_name,
                    tenant_id=tenant.id
                )
                db.add(module)
                db.flush()

            # Create resources for this module in this tenant
            for resource_name in resource_names:
                existing = db.query(Resource).filter(
                    Resource.module_id == module.id,
                    Resource.name == resource_name,
                    Resource.tenant_id == tenant.id
                ).first()

                if not existing:
                    resource = Resource(
                        module_id=module.id,
                        name=resource_name,
                        display_name=resource_name.replace('-', ' ').title(),
                        tenant_id=tenant.id
                    )
                    db.add(resource)

        db.commit()

        # Count resources in this tenant
        resource_count = db.query(Resource).filter(
            Resource.tenant_id == tenant.id
        ).count()
        print(f"  ✅ {resource_count} resources initialized\n")

    print("="*60)
    print("✅ ALL TENANTS NOW HAVE COMPLETE RESOURCE STRUCTURE")
    print("="*60)
    print("\nEach company now has:")
    print("  • All modules")
    print("  • All resources")
    print("  • Ready for role template creation")
    print("  • Ready for permission assignment")

except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
