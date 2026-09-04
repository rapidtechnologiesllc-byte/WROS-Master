#!/usr/bin/env python3
"""Initialize organizational hierarchy for all tenants"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.org_structure import OrgPosition, OrgNode
from app.services.org_structure_service import (
    init_default_positions,
    create_root_ceo_node,
    setup_approval_chains,
)
from datetime import datetime

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    print("[INITIALIZE ORG HIERARCHY]")
    print("="*60 + "\n")

    # Get all tenants
    tenants = db.query(Tenant).all()
    print(f"Found {len(tenants)} tenant(s):\n")

    for tenant in tenants:
        print(f"Processing {tenant.name} (id={tenant.id})...")

        # Check if CEO node already exists
        ceo_node = db.query(OrgNode).filter(
            OrgNode.tenant_id == tenant.id,
            OrgNode.name == "CEO"
        ).first()

        if ceo_node:
            print(f"  ✅ CEO node already exists (id={ceo_node.id})")
        else:
            # Initialize positions (global, not per-tenant)
            pos_result = init_default_positions(db)
            print(f"  ✅ Positions: {pos_result['created']} created, {pos_result['updated']} updated")

            # Create CEO node
            ceo_node = create_root_ceo_node(db, tenant.id, name="CEO")
            print(f"  ✅ Created CEO node (id={ceo_node.id})")

            # Setup approval chains
            chain_result = setup_approval_chains(db, tenant.id)
            print(f"  ✅ Created {chain_result['approval_chains_created']} approval chains")

    db.commit()

    print("\n" + "="*60)
    print("✅ ORG HIERARCHY INITIALIZED FOR ALL TENANTS")
    print("="*60)
    print("\nEach tenant now has:")
    print("  • Root CEO node")
    print("  • 10 organizational positions (CEO, Partner, BU Head, ...)")
    print("  • Approval chains for workflows (TIMESHEET, OFFER_LETTER, etc)")
    print("\nFrontend can now display organizational hierarchy with tenant names.")

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
