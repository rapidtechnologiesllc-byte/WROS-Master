#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "OnboardingModule-Backend"))

from app.core.database import SessionLocal
from app.models.user import Users

db = SessionLocal()

# Check the Super User
user = db.query(Users).filter(Users.UserEmail == "testsuper@blitzenx.com").first()

if user:
    print(f"User found: {user.UserEmail}")
    print(f"  UserName: {user.UserName}")
    print(f"  UserID: {user.UserID}")
    print(f"  UserRole: {user.UserRole}")
    print(f"  business_unit_id: {user.business_unit_id}")
    print(f"  tenant_id: {user.tenant_id}")
else:
    print("User not found!")

# Also check how many business units exist
bus_units = db.query(__import__('app.models.rbac', fromlist=['BusinessUnit']).BusinessUnit).all()
print(f"\nBusiness units in database: {len(bus_units)}")
for bu in bus_units:
    print(f"  - ID {bu.id}: {bu.bu_name}")

db.close()
