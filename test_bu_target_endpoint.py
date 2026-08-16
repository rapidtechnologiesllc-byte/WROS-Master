#!/usr/bin/env python3
"""Test the BU revenue target endpoint to diagnose the error."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.rbac import BusinessUnit
from app.services.revenue_target_service import set_bu_revenue_target, get_bu_target_vs_actual

db = SessionLocal()

print("\n" + "=" * 70)
print("TESTING BU REVENUE TARGET ENDPOINT")
print("=" * 70)

# Get test business unit
tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()
if not tenant:
    print("    [FAIL] Tenant not found")
    sys.exit(1)

business_units = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant.id).all()
print(f"\nAvailable Business Units in {tenant.name}:")
for bu in business_units:
    print(f"    - ID: {bu.id} | Name: {bu.name} | Code: {bu.bu_code}")

if not business_units:
    print("    [FAIL] No business units found!")
    sys.exit(1)

bu = business_units[0]

# Test setting a target
print(f"\nTesting revenue target creation for BU: {bu.name} (ID: {bu.id})")
try:
    target = set_bu_revenue_target(
        db,
        business_unit_id=bu.id,
        target_period='ANNUAL',
        fiscal_year=2026,
        target_amount_usd_cents=350000*100,  # $350,000 USD
        created_by='superuser@blitzenx.com',
        tenant_id=tenant.id,
        notes='Test target'
    )
    print(f"    [OK] Target created successfully")
    print(f"         ID: {target.id}")
    print(f"         Amount: ${target.target_amount_usd_cents / 100:,.0f} USD")
except Exception as e:
    print(f"    [FAIL] Error creating target:")
    print(f"         Type: {type(e).__name__}")
    print(f"         Message: {str(e)}")
    import traceback
    traceback.print_exc()

# Test retrieving the target
print(f"\nRetrieving target for {bu.name}...")
try:
    result = get_bu_target_vs_actual(db, bu.id, 'ANNUAL', 2026)
    print(f"    [OK] Target retrieved successfully")
    print(f"         Status: {result.get('status', 'N/A')}")
    print(f"         Target: ${result.get('target_amount_usd_cents', 0) / 100:,.0f} USD")
    print(f"         Actual: ${result.get('actual_usd_cents', 0) / 100:,.0f} USD")
except Exception as e:
    print(f"    [FAIL] Error retrieving target:")
    print(f"         Type: {type(e).__name__}")
    print(f"         Message: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
db.close()
