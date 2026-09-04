#!/usr/bin/env python3
import logging
"""Diagnose all remaining issues after fixes."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.tenant import Tenant
from app.models.candidate import Candidate
from app.models.opportunity import Opportunity

db = SessionLocal()

print("=" * 60)
print("WROS SYSTEM DIAGNOSTICS")
print("=" * 60)

# Check SuperUser Tenant
print("\n[1] SuperUser Tenant Assignment:")
superuser = db.query(Users).filter(Users.UserEmail.ilike('%superuser%')).first()
tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()

if superuser:
    print(f"    Email: {superuser.UserEmail}")
    print(f"    Current tenant_id: {superuser.tenant_id}")
    print(f"    Expected tenant_id: {tenant.id if tenant else 'NO TENANT'}")
    if superuser.tenant_id == (tenant.id if tenant else None):
        print("    ✅ CORRECT")
    else:
        print("    ❌ INCORRECT - FIX NEEDED")
else:
    print("    ❌ SuperUser not found!")

# Check Candidates BU Context
print("\n[2] Candidates Business Unit Context:")
candidates = db.query(Candidate).all()
with_bu = [c for c in candidates if c.bu_context_id]
print(f"    Total candidates: {len(candidates)}")
print(f"    With BU context: {len(with_bu)}/{len(candidates)}")
if len(with_bu) == len(candidates):
    print("    ✅ ALL HAVE BU CONTEXT")
else:
    print(f"    ❌ {len(candidates) - len(with_bu)} MISSING BU CONTEXT")

# Check Opportunities
print("\n[3] Opportunities/Job Assignments:")
opportunities = db.query(Opportunity).all()
print(f"    Total opportunities: {len(opportunities)}")
if len(opportunities) > 0:
    print("    ✅ OPPORTUNITIES EXIST")
else:
    print("    ❌ NO OPPORTUNITIES CREATED")

# Check for Thunder/Agent assignments
print("\n[4] Thunder AI Recruiter Status:")
print("    ℹ️  Thunder auto-assignment happens on scheduler cycle")
print("    ℹ️  Check logs: /thunder endpoint or scheduler logs")

db.close()

print("\n" + "=" * 60)
print("END DIAGNOSTICS")
print("=" * 60)
