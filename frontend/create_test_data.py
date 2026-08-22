#!/usr/bin/env python3
"""
Create test data for BU Scoping tests
Runs: python3 create_test_data.py
"""

import requests
import json

# Backend API URL
API_URL = "http://localhost:8080"

# Test data to create
BUS = [
    {"id": "bu-001", "name": "North America", "code": "NA"},
    {"id": "bu-002", "name": "Europe", "code": "EU"},
]

USERS = [
    # BU Heads
    {"email": "buhead.na@blitzenx.com", "password": "BUHeadNA@123", "name": "Alice North America", "role": "bu_head", "bu": "bu-001"},
    {"email": "buhead.eu@blitzenx.com", "password": "BUHeadEU@123", "name": "Bob Europe", "role": "bu_head", "bu": "bu-002"},

    # Recruiters BU 1
    {"email": "recruiter.na.1@blitzenx.com", "password": "RecruiterNA1@123", "name": "Charlie NA Recruiter 1", "role": "recruiter", "bu": "bu-001"},
    {"email": "recruiter.na.2@blitzenx.com", "password": "RecruiterNA2@123", "name": "Diana NA Recruiter 2", "role": "recruiter", "bu": "bu-001"},

    # Recruiters BU 2
    {"email": "recruiter.eu.1@blitzenx.com", "password": "RecruiterEU1@123", "name": "Eve EU Recruiter 1", "role": "recruiter", "bu": "bu-002"},
    {"email": "recruiter.eu.2@blitzenx.com", "password": "RecruiterEU2@123", "name": "Frank EU Recruiter 2", "role": "recruiter", "bu": "bu-002"},

    # HR Managers
    {"email": "hr.na.1@blitzenx.com", "password": "HRNA1@123", "name": "Grace NA HR Manager", "role": "hr_manager", "bu": "bu-001"},
    {"email": "hr.eu.1@blitzenx.com", "password": "HREU1@123", "name": "Henry EU HR Manager", "role": "hr_manager", "bu": "bu-002"},

    # Hiring Managers
    {"email": "hm.na.1@blitzenx.com", "password": "HMNA1@123", "name": "Iris NA Hiring Manager", "role": "hiring_manager", "bu": "bu-001"},
    {"email": "hm.eu.1@blitzenx.com", "password": "HMEU1@123", "name": "Jack EU Hiring Manager", "role": "hiring_manager", "bu": "bu-002"},
]

def create_business_units():
    """Create business units"""
    print("\n📍 Creating Business Units...")
    for bu in BUS:
        try:
            response = requests.post(
                f"{API_URL}/api/v1/business-units",
                json=bu,
                timeout=5
            )
            if response.status_code in [200, 201]:
                print(f"  ✅ Created BU: {bu['name']}")
            else:
                print(f"  ⚠️  {bu['name']}: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error creating {bu['name']}: {e}")

def create_users():
    """Create test users"""
    print("\n👥 Creating Test Users...")
    for user in USERS:
        try:
            payload = {
                "email": user["email"],
                "password": user["password"],
                "name": user["name"],
                "role": user["role"],
                "business_unit_id": user["bu"],
            }

            response = requests.post(
                f"{API_URL}/api/v1/users",
                json=payload,
                timeout=5
            )

            if response.status_code in [200, 201]:
                print(f"  ✅ Created: {user['email']} ({user['role']})")
            else:
                print(f"  ⚠️  {user['email']}: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error creating {user['email']}: {e}")

def main():
    print("=" * 60)
    print("  BU SCOPING TEST DATA CREATION")
    print("=" * 60)

    print(f"\nℹ️  Backend URL: {API_URL}")
    print(f"ℹ️  Creating {len(BUS)} Business Units")
    print(f"ℹ️  Creating {len(USERS)} Test Users")

    create_business_units()
    create_users()

    print("\n" + "=" * 60)
    print("  ✅ TEST DATA CREATION COMPLETE")
    print("=" * 60)
    print("\nYou can now run the tests:")
    print("  npm run test:e2e -- tests/e2e/bu-scoping.spec.js")
    print("\nTest users created:")
    for user in USERS:
        print(f"  • {user['email']} / {user['password']}")

if __name__ == "__main__":
    main()
