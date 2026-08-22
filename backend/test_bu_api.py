#!/usr/bin/env python3
"""Test the BU Head Dashboard API with a valid JWT token."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "OnboardingModule-Backend"))

from app.core.database import SessionLocal
from app.models.user import Users
from app.core.security import create_access_token
from datetime import timedelta

db = SessionLocal()

# Get the Super User
user = db.query(Users).filter(Users.UserEmail == "testsuper@blitzenx.com").first()

if not user:
    print("Super User not found!")
    sys.exit(1)

print(f"User found: {user.UserEmail}")
print(f"  UserRole: {user.UserRole}")
print(f"  UserID: {user.UserID}")
print(f"  business_unit_id: {user.business_unit_id}")

# Create a JWT token manually
token_data = {
    "sub": user.UserEmail,
    "type": user.UserRole,
    "name": user.UserName,
}

token = create_access_token(token_data, expires_delta=timedelta(hours=1))
print(f"\nGenerated JWT token:\n{token}")

# Now test the API endpoint manually
import requests

headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8080/dashboards/bu-head/summary",
    headers=headers
)

print(f"\nAPI Response Status: {response.status_code}")
print(f"API Response Body: {response.text}")

db.close()
