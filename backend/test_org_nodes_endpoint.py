#!/usr/bin/env python3
"""Test the /org/nodes endpoint to see what it returns"""
import sys, os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.org_structure import OrgNode
from app.schemas.org_structure import OrgNodeResponse
import json

db = SessionLocal()

try:
    print("[TEST ORG NODES ENDPOINT]")
    print("="*60 + "\n")

    # Simulate tenant 3 (BlitzenX)
    tenant_id = 3

    # This is what the endpoint does
    nodes = db.query(OrgNode).filter(OrgNode.tenant_id == tenant_id).all()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_name = tenant.name if tenant else f"Tenant {tenant_id}"

    print(f"Found {len(nodes)} node(s) for tenant {tenant_id} ({tenant_name})\n")

    result = []
    for node in nodes:
        node_dict = OrgNodeResponse.from_orm(node).dict()
        print(f"From ORM: {node_dict}")
        node_dict['tenant_name'] = tenant_name
        print(f"After adding tenant_name: {node_dict}")
        result.append(OrgNodeResponse(**node_dict))

    print("\nFinal response as JSON:")
    response_json = [r.dict() for r in result]
    print(json.dumps(response_json, indent=2, default=str))

except Exception as e:
   logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
