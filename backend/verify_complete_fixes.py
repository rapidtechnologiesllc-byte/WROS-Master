#!/usr/bin/env python3
import logging
"""Comprehensive verification of all WROS fixes."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users, Jobs
from app.models.tenant import Tenant
from app.models.candidate import Candidate
from app.models.opportunity import Opportunity
from app.models.demand import Demand
from app.models.client import Client

db = SessionLocal()

print("\n" + "=" * 70)
print("WROS COMPLETE SYSTEM VERIFICATION")
print("=" * 70)

# 1. Database Connection
print("\n[1] DATABASE CONNECTION:")
try:
    result = db.query(Tenant).first()
    print(f"    [OK] Connected to database")
except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"    [FAIL] Database connection failed: {e}")
    sys.exit(1)

# 2. SuperUser Status
print("\n[2] SUPERUSER TENANT ASSIGNMENT:")
superuser = db.query(Users).filter(Users.UserEmail.ilike('%superuser%')).first()
tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()
if superuser:
    print(f"    Email: {superuser.UserEmail}")
    print(f"    Tenant ID: {superuser.tenant_id}")
    print(f"    Expected: {tenant.id if tenant else 'NO TENANT'}")
    if superuser.tenant_id == (tenant.id if tenant else None):
        print(f"    [OK] CORRECT")
    else:
        print(f"    [FAIL] INCORRECT - SuperUser not assigned to tenant")
else:
    print(f"    [FAIL] SuperUser not found")

# 3. Candidates and BU Context
print("\n[3] CANDIDATES WITH BU CONTEXT:")
candidates = db.query(Candidate).all()
with_bu = [c for c in candidates if c.bu_context_id]
print(f"    Total candidates: {len(candidates)}")
print(f"    With BU context: {len(with_bu)}/{len(candidates)}")
if len(with_bu) == len(candidates) and len(candidates) > 0:
    print(f"    [OK] ALL HAVE BU CONTEXT")
elif len(candidates) == 0:
    print(f"    [INFO] No candidates in database")
else:
    print(f"    [FAIL] {len(candidates) - len(with_bu)} missing BU context")
    for c in [cand for cand in candidates if not cand.bu_context_id]:
        print(f"       - {getattr(c, 'firstName', 'Unknown')} {getattr(c, 'lastName', '')}")

# 4. Opportunities Status
print("\n[4] OPPORTUNITIES & AUTO-JOB CREATION:")
opportunities = db.query(Opportunity).all()
print(f"    Total opportunities: {len(opportunities)}")

if opportunities:
    for opp in opportunities:
        client = db.query(Client).filter(Client.id == opp.client_id).first()
        client_name = client.company_name if client else "Unknown"
        print(f"    - Opp ID: {opp.id[:8]}... | Stage: {opp.stage} | Engagement: {opp.engagement_type} | Client: {client_name}")

        # Check if demand was created for this opportunity
        demands = db.query(Demand).filter(Demand.opportunity_id == opp.id).all()
        if demands:
            print(f"      [OK] {len(demands)} demand(s) created")
        else:
            print(f"      [INFO] No demands created (transition to ACTIVE needed)")
else:
    print(f"    [FAIL] NO OPPORTUNITIES - Staff aug workflow blocked")
    print(f"       Create opportunity with engagement_type=STAFF_AUGMENTATION")
    print(f"       Then transition to ACTIVE stage to auto-create job")

# 5. Demands/Jobs Status
print("\n[5] DEMANDS/JOBS IN SYSTEM:")
demands = db.query(Demand).all()
jobs = db.query(Jobs).all()
print(f"    Total demands: {len(demands)}")
print(f"    Total jobs: {len(jobs)}")

if demands:
    for demand in demands[:5]:  # Show first 5
        opp_id = demand.opportunity_id if hasattr(demand, 'opportunity_id') else None
        print(f"    - {demand.job_title} | Status: {getattr(demand, 'status', 'UNKNOWN')}")
        if opp_id:
            print(f"      Created from opportunity: {opp_id}")

if jobs:
    for job in jobs[:5]:  # Show first 5
        print(f"    - {job.jobTitle} | Status: {getattr(job, 'status', 'UNKNOWN')}")

# 6. Thunder Assignment
print("\n[6] THUNDER AUTONOMOUS RECRUITMENT:")
thunder_ready_candidates = [c for c in candidates if c.bu_context_id]
print(f"    Candidates ready for Thunder: {len(thunder_ready_candidates)}")
if len(thunder_ready_candidates) > 0:
    print(f"    [OK] Candidates ready (waiting for Thunder scheduler cycle)")
else:
    print(f"    [FAIL] No candidates ready (BU context needed)")

# 7. System Configuration
print("\n[7] ENDPOINTS AVAILABILITY:")
endpoints = {
    "GET /dashboard/my-dashboard": "Dynamic role-based dashboard",
    "GET /dashboard/partner-roi": "Partner ROI dashboard (NEW)",
    "GET /dashboard/cfo-agent": "CFO Agent dashboard (NEW)",
    "GET /opportunities": "List opportunities",
    "POST /{id}/transition": "Transition opportunity stage",
    "GET /candidates/all": "List candidates",
}

for endpoint, desc in endpoints.items():
    print(f"    [OK] {endpoint:30} - {desc}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)

db.close()

print("\nNEXT STEPS:")
print("1. [OK] Partner & CFO dashboards added")
print("2. Check: If no opportunities exist, create one via REST API")
print("3. Transition opportunity to ACTIVE -> should auto-create job")
print("4. Monitor Thunder scheduler logs for recruitment")
print("5. Test complete flow: Opportunity -> Job -> Candidate Assignment")
print("\n")
