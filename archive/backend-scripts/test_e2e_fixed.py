#!/usr/bin/env python3
"""End-to-end test of the complete fixed system."""

import requests
import json
import sys

BASE_URL = "http://localhost:8081"
RECRUITER_EMAIL = "recruiter@test.com"
RECRUITER_PASSWORD = "Recruiter@123"

def test_login():
    """Test login and get JWT token."""
    print("\n✓ TEST 1: Login")
    url = f"{BASE_URL}/auth/login"
    payload = {
        "email": RECRUITER_EMAIL,
        "password": RECRUITER_PASSWORD
    }

    try:
        response = requests.post(url, json=payload)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"  ✅ Login successful")
            print(f"  Token: {token[:30]}...")
            return token
        else:
            print(f"  ❌ Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def test_get_candidates(token):
    """Test fetching candidates list."""
    print("\n✓ TEST 2: Get Candidates List")
    url = f"{BASE_URL}/api/v1/candidates/all"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Candidates fetched successfully")
            print(f"  Count: {len(data) if isinstance(data, list) else 'N/A'}")
            return True
        else:
            print(f"  ❌ Failed to fetch candidates: {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_create_candidate(token):
    """Test creating a new candidate."""
    print("\n✓ TEST 3: Create Candidate")
    url = f"{BASE_URL}/api/v1/candidates/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "candidateEmail": "john.doe@example.com",
        "candidateName": "John Doe",
        "candidatePhone": "+1234567890",
        "candidateExperience": 5,
        "candidateCurrentCompany": "Tech Corp",
        "candidateCurrentPosition": "Senior Engineer",
        "candidateYearsExperience": 5
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            print(f"  ✅ Candidate created successfully")
            candidate_id = data.get("candidateID") or data.get("id")
            print(f"  Candidate ID: {candidate_id}")
            return True
        else:
            print(f"  ❌ Failed to create candidate: {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_permission_check():
    """Test that unauthorized requests are rejected."""
    print("\n✓ TEST 4: Permission Check (No Token)")
    url = f"{BASE_URL}/api/v1/candidates/all"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        print(f"  Status: {response.status_code}")

        if response.status_code == 401 or response.status_code == 403:
            print(f"  ✅ Unauthorized request correctly rejected")
            return True
        else:
            print(f"  ❌ Expected 401/403, got {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("COMPLETE SYSTEM END-TO-END TEST")
    print("=" * 60)

    results = []

    # Test 1: Login
    token = test_login()
    if token:
        results.append(("Login", True))
    else:
        print("❌ Cannot proceed without valid token")
        results.append(("Login", False))
        print_summary(results)
        return

    # Test 2: Get Candidates
    if test_get_candidates(token):
        results.append(("Get Candidates", True))
    else:
        results.append(("Get Candidates", False))

    # Test 3: Create Candidate
    if test_create_candidate(token):
        results.append(("Create Candidate", True))
    else:
        results.append(("Create Candidate", False))

    # Test 4: Permission Check
    if test_permission_check():
        results.append(("Permission Check", True))
    else:
        results.append(("Permission Check", False))

    print_summary(results)

def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print("=" * 60)
    print(f"RESULT: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 SYSTEM IS 100/100 - ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"⚠️  System is {int(passed/total*100)}/100 - Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
