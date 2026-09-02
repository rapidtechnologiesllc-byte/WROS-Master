#!/usr/bin/env python3
import logging
"""Fix: Assign SuperUser to a business unit context so dashboards load."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.business_unit_context import BusinessUnitContext

db = SessionLocal()

print("\n" + "=" * 70)
print("FIXING SUPERUSER BUSINESS UNIT ASSIGNMENT")
print("=" * 70)

# Get tenant
tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()
if not tenant:
    print("\n[FAIL] BlitzenX tenant not found")
    sys.exit(1)

# Get or create default business unit
bu = db.query(BusinessUnit).filter(
    BusinessUnit.tenant_id == tenant.id,
    BusinessUnit.bu_code == "NA"
).first()

if not bu:
    print("\n[ACTION] Creating default Business Unit...")
    bu = BusinessUnit(
        name="North America",
        description="Default Business Unit",
        tenant_id=tenant.id,
        bu_code="NA"
    )
    db.add(bu)
    db.commit()
    print(f"    [OK] Created: {bu.name}")
else:
    print(f"\n[OK] Using existing Business Unit: {bu.name} (ID: {bu.id})")

# Get or create BusinessUnitContext
bu_context = db.query(BusinessUnitContext).filter(
    BusinessUnitContext.business_unit_id == bu.id,
    BusinessUnitContext.tenant_id == tenant.id
).first()

if not bu_context:
    print(f"\n[ACTION] Creating BusinessUnitContext...")
    bu_context = BusinessUnitContext(
        tenant_id=tenant.id,
        business_unit_id=bu.id,
        active=True
    )
    db.add(bu_context)
    db.commit()
    print(f"    [OK] Created BusinessUnitContext")
else:
    print(f"\n[OK] Using existing BusinessUnitContext")

# Assign SuperUser to business unit context
superuser = db.query(Users).filter(Users.UserEmail.ilike('%superuser%')).first()
if not superuser:
    print("\n[FAIL] SuperUser not found")
    sys.exit(1)

print(f"\nAssigning SuperUser to {bu.name}...")
superuser.bu_context_id = bu_context.id
db.commit()
print(f"    [OK] SuperUser assigned to bu_context_id: {superuser.bu_context_id}")

# Verify
superuser = db.query(Users).filter(Users.UserID == superuser.UserID).first()
print(f"\nVerification:")
print(f"    SuperUser Email: {superuser.UserEmail}")
print(f"    Business Unit ID (derived): {superuser.business_unit_id}")
print(f"    BU Context ID: {superuser.bu_context_id}")
print(f"    Tenant ID: {superuser.tenant_id}")

if superuser.bu_context_id and superuser.tenant_id:
    print(f"\n[SUCCESS] SuperUser ready for executive dashboards!")
else:
    print(f"\n[FAIL] Assignment incomplete")

db.close()
print("\n" + "=" * 70)
