#!/usr/bin/env python3
"""Demonstrate the complete opportunity -> job auto-creation workflow."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.opportunity import Opportunity
from app.models.demand import Demand
from app.services.opportunity_service import transition_stage
import uuid
from datetime import datetime, timedelta

db = SessionLocal()

print("\n" + "=" * 70)
print("OPPORTUNITY -> JOB AUTO-CREATION WORKFLOW DEMONSTRATION")
print("=" * 70)

# Step 1: Get tenant and create test client if needed
print("\n[Step 1] Setting up test data...")
tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()
if not tenant:
    print("    [FAIL] BlitzenX tenant not found")
    sys.exit(1)

# Find or create test client
client = db.query(Client).filter(Client.company_name == 'Test Corp').first()
if not client:
    client = Client(
        id=str(uuid.uuid4()),
        company_name='Test Corp',
        status='QUALIFICATION',
        tenant_id=tenant.id,
        created_at=datetime.utcnow()
    )
    db.add(client)
    db.commit()
    print(f"    [OK] Created test client: Test Corp (ID: {client.id[:8]}...)")
else:
    print(f"    [OK] Using existing client: Test Corp (ID: {client.id[:8]}...)")

# Step 2: Create opportunity in QUALIFICATION stage
print("\n[Step 2] Creating staff augmentation opportunity...")
opportunity = Opportunity(
    id=str(uuid.uuid4()),
    tenant_id=tenant.id,
    client_id=client.id,
    stage='QUALIFICATION',
    engagement_type='STAFF_AUGMENTATION',
    revenue_value_usd_cents=500000,  # $5,000 USD
    currency='USD',
    probability_pct=10,
    expected_close_date=datetime.utcnow() + timedelta(days=30),
    created_at=datetime.utcnow()
)
db.add(opportunity)
db.commit()
print(f"    [OK] Created opportunity: {opportunity.id[:8]}...")
print(f"         - Stage: QUALIFICATION")
print(f"         - Engagement Type: STAFF_AUGMENTATION")
print(f"         - Revenue: $5,000 USD")

# Step 3: Transition to PROSPECT (intermediate stage)
print("\n[Step 3] Transitioning to PROSPECT stage...")
result = transition_stage(db, opportunity, 'PROSPECT', changed_by='system')
db.commit()
print(f"    [OK] Transitioned to PROSPECT")

# Check if jobs were created (shouldn't be yet)
demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
print(f"    Demands created: {len(demands)} (expected 0)")

# Step 4: Transition to PROPOSAL
print("\n[Step 4] Transitioning to PROPOSAL stage...")
result = transition_stage(db, opportunity, 'PROPOSAL', changed_by='system')
db.commit()
print(f"    [OK] Transitioned to PROPOSAL")

demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
print(f"    Demands created: {len(demands)} (expected 0)")

# Step 5: Transition to NEGOTIATION
print("\n[Step 5] Transitioning to NEGOTIATION stage...")
result = transition_stage(db, opportunity, 'NEGOTIATION', changed_by='system')
db.commit()
print(f"    [OK] Transitioned to NEGOTIATION")

demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
print(f"    Demands created: {len(demands)} (expected 0)")

# Step 6: Transition to CONTRACT
print("\n[Step 6] Transitioning to CONTRACT stage...")
result = transition_stage(db, opportunity, 'CONTRACT', changed_by='system')
db.commit()
print(f"    [OK] Transitioned to CONTRACT")

demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
print(f"    Demands created: {len(demands)} (expected 0)")

# Step 7: THE MAGIC - Transition to ACTIVE (should auto-create job)
print("\n[Step 7] Transitioning to ACTIVE - THIS SHOULD AUTO-CREATE JOB...")
result = transition_stage(db, opportunity, 'ACTIVE', changed_by='system')
db.commit()
print(f"    [OK] Transitioned to ACTIVE")

# Check results
demands = db.query(Demand).filter(Demand.opportunity_id == opportunity.id).all()
print(f"\n    RESULT: {len(demands)} demand(s) created!")

if len(demands) > 0:
    demand = demands[0]
    print(f"\n    [SUCCESS] Auto-created job:")
    print(f"    - Job Title: {demand.job_title}")
    print(f"    - Status: {getattr(demand, 'status', 'DRAFT')}")
    print(f"    - Opportunity Link: {demand.opportunity_id}")
    print(f"    - Client: {client.company_name}")
else:
    print(f"\n    [FAIL] No job was auto-created!")

# Step 8: Summary
print("\n" + "=" * 70)
print("WORKFLOW SUMMARY")
print("=" * 70)
print(f"""
This demonstration shows:

1. Create Opportunity in QUALIFICATION stage
   - engagement_type must be 'STAFF_AUGMENTATION'
   - stage can be any value initially

2. Transition through stages:
   QUALIFICATION -> PROSPECT -> PROPOSAL -> NEGOTIATION -> CONTRACT -> ACTIVE

3. When reaching ACTIVE stage:
   - If engagement_type is STAFF_AUGMENTATION -> AUTO-CREATE Demand (job)
   - If engagement_type is PROJECT_BASED -> AUTO-CREATE Project

4. Auto-created jobs have:
   - job_title: "Staff Augmentation - <opp_id>"
   - status: DRAFT
   - Linked back to opportunity

REST API Usage:
1. Create opportunity:
   POST /opportunities
   {{
     "client_id": "...",
     "revenue_value_usd_cents": 500000,
     "currency": "USD",
     "stage": "QUALIFICATION",
     "engagement_type": "STAFF_AUGMENTATION"
   }}

2. Transition to ACTIVE:
   POST /opportunities/{{opportunity_id}}/transition
   {{
     "new_stage": "ACTIVE"
   }}

3. Job will be auto-created in response (if success)
""")

db.close()
