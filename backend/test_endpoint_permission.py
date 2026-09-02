#!/usr/bin/env python3
"""Test if endpoint permission is blocking the org nodes"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.org_structure import OrgNode
from app.models.tenant import Tenant

db = SessionLocal()

try:
    print("[TEST ENDPOINT PERMISSION]")
    print("="*60 + "\n")

    # Get Super User
    super_user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()
    print(f"Super User: {super_user.UserEmail}")
    print(f"  Tenant ID: {super_user.tenant_id}")
    print(f"  Role: {super_user.UserRole}")
    print()

    # Get org nodes for their tenant
    tenant_id = super_user.tenant_id
    nodes = db.query(OrgNode).filter(OrgNode.tenant_id == tenant_id).all()
    print(f"Org nodes for tenant {tenant_id}: {len(nodes)}")

    for node in nodes:
        print(f"  - {node.name} (id={node.id})")

    # Check tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    print(f"\nTenant: {tenant.name}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
