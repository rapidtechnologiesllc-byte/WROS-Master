#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "OnboardingModule-Backend"))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.rbac import BusinessUnit

db = SessionLocal()

# Get or create a business unit for testing
bu = db.query(BusinessUnit).first()
if not bu:
    print("No business units found! Creating one...")
    bu = BusinessUnit(bu_name="Test BU", bu_code="TEST", tenant_id=1)
    db.add(bu)
    db.commit()
    db.refresh(bu)

print(f"Using Business Unit: {bu.id} - {bu.bu_name if hasattr(bu, 'bu_name') else 'Unknown'}")

# Update the Super User with the business unit
user = db.query(Users).filter(Users.UserEmail == "testsuper@blitzenx.com").first()
if user:
    user.business_unit_id = bu.id
    db.commit()
    print(f"Updated Super User: business_unit_id = {user.business_unit_id}")
else:
    print("Super User not found!")

db.close()
