#!/usr/bin/env python3
"""
WROS Application Page Audit Script
Tests every menu item to identify pages that load but show no data
"""

import requests
import json
import time
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://localhost:3000"
BACKEND_API = "http://localhost:8080"

# Test user token (we'll need to login first)
TEST_EMAIL = "recruiter@test.com"
TEST_PASSWORD = "TestRecruiter@123"

session = requests.Session()

def login():
    """Login and get JWT token"""
    print("\n[*] Attempting login...")

    login_url = f"{BACKEND_API}/auth/login"
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }

    try:
        response = requests.post(login_url, json=payload)
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token", "")
            print(f"[✓] Login successful, token: {token[:20]}...")
            return token
        else:
            print(f"[✗] Login failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return None
    except Exception as e:
        print(f"[✗] Login error: {e}")
        return None

def check_page_load(url: str) -> Tuple[bool, int, str]:
    """
    Check if a page loads (HTTP status)
    Returns: (loads_ok, status_code, content_preview)
    """
    try:
        response = requests.get(url, timeout=5)
        status = response.status_code
        content_preview = response.text[:200] if response.text else ""
        return (status < 400, status, content_preview)
    except requests.exceptions.Timeout:
        return (False, 0, "Timeout")
    except Exception as e:
        return (False, 0, str(e))

def check_api_endpoint(endpoint: str, token: str = None) -> Tuple[int, Dict]:
    """
    Check an API endpoint for data
    Returns: (status_code, response_data)
    """
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.get(f"{BACKEND_API}{endpoint}", headers=headers, timeout=5)
        status = response.status_code

        try:
            data = response.json()
        except:
            data = {"error": "Not JSON"}

        return (status, data)
    except Exception as e:
        return (0, {"error": str(e)})

def has_data(response_data: Dict) -> bool:
    """
    Check if response contains actual data
    Returns True if data is present, False if empty
    """
    if not response_data:
        return False

    if isinstance(response_data, dict):
        # Check for empty arrays or null data
        if "data" in response_data:
            if isinstance(response_data["data"], list):
                return len(response_data["data"]) > 0
            return response_data["data"] is not None

        # Check if dict has any meaningful content
        if len(response_data) == 0:
            return False

        # Filter out common meta fields
        meta_fields = {"status", "message", "error", "code", "timestamp"}
        content = {k: v for k, v in response_data.items() if k not in meta_fields}

        if len(content) == 0:
            return False

        # Check if all values are empty
        has_content = any(v for v in content.values() if v)
        return has_content

    if isinstance(response_data, list):
        return len(response_data) > 0

    return bool(response_data)

# Frontend pages to test (by menu navigation)
FRONTEND_PAGES = {
    "Recruitment": {
        "Candidates": "/candidates",
        "Jobs": "/jobs",
        "Submissions": "/submissions",
        "Interviews": "/interviews",
        "Offer Letters": "/offer-letters",
        "Intervention Queue": "/intervention-queue",
        "Rehire Approval": "/rehire-approval",
        "Candidate Review": "/candidate-review",
        "Risk Dashboard": "/risk-dashboard",
        "Thunder Analytics": "/thunder-analytics",
        "Bulk Launch": "/bulk-launch",
    },
    "Workforce": {
        "Employees": "/employees",
        "Allocations": "/allocations",
    },
    "Sales": {
        "Client Management": "/clients",
    },
    "Projects": {
        "Project Management": "/projects",
    },
    "Finance": {
        "Invoices": "/invoices",
        "Reports": "/reports",
    },
    "Admin": {
        "Users & Access Control": "/users",
        "Role Templates": "/role-templates",
        "Certifications": "/certifications",
        "Admin Settings": "/admin-settings",
    },
    "Executive": {
        "CEO Dashboard": "/ceo-dashboard",
        "CFO Dashboard": "/cfo-dashboard",
        "Partner Dashboard": "/partner-dashboard",
        "Executive Signal": "/executive-signal",
    },
    "Personal": {
        "Dashboard": "/dashboard",
        "My Tasks": "/my-tasks",
        "My Timesheet": "/my-timesheet",
        "My Expenses": "/my-expenses",
        "My Referrals": "/my-referrals",
    },
}

# Backend API endpoints to test for data
BACKEND_ENDPOINTS = {
    "Candidates": "/api/v1/candidates",
    "Jobs": "/api/v1/jobs/all",
    "Submissions": "/api/v1/submissions",
    "Interviews": "/api/v1/interviews",
    "Employees": "/api/v1/employees",
    "Users": "/api/v1/users",
    "Invoices": "/api/v1/invoices",
    "Projects": "/api/v1/projects",
    "Reports": "/api/v1/reports",
}

def main():
    print("=" * 80)
    print("WROS APPLICATION PAGE AUDIT")
    print("=" * 80)

    # Try to get auth token
    token = login()
    if not token:
        print("\n[!] Warning: Could not authenticate. Testing without token.")

    print("\n" + "=" * 80)
    print("FRONTEND PAGES TEST")
    print("=" * 80)

    no_data_pages = []

    for section, pages in FRONTEND_PAGES.items():
        print(f"\n[*] Section: {section}")
        print("-" * 80)

        for page_name, path in pages.items():
            url = f"{BASE_URL}{path}"
            loads_ok, status, preview = check_page_load(url)

            # Quick content check (very basic)
            is_empty = len(preview) < 100 or "empty" in preview.lower()

            status_icon = "✓" if loads_ok else "✗"
            data_icon = "?" # Can't tell from frontend alone

            print(f"  {status_icon} {page_name:<30} {status:>3} | {data_icon}")

            if not loads_ok:
                print(f"    └─ Error: {preview[:50]}")
            elif is_empty:
                no_data_pages.append((section, page_name, url, status))

    print("\n" + "=" * 80)
    print("BACKEND API ENDPOINTS TEST")
    print("=" * 80)

    for endpoint_name, endpoint in BACKEND_ENDPOINTS.items():
        status, data = check_api_endpoint(endpoint, token)
        has_content = has_data(data)

        data_icon = "✓" if has_content else "✗"
        status_icon = "✓" if status < 400 else "✗"

        print(f"  {status_icon} {endpoint_name:<25} {status:>3} | {data_icon} Data: {has_content}")

        if status >= 400:
            print(f"    └─ Error: {data.get('error', 'Unknown error')}")
        elif not has_content:
            print(f"    └─ No data returned")
            # Show sample response
            if isinstance(data, dict):
                for key in list(data.keys())[:3]:
                    print(f"       - {key}: {str(data[key])[:50]}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if no_data_pages:
        print(f"\n[!] Found {len(no_data_pages)} pages that might have no data:\n")
        for section, name, url, status in no_data_pages:
            print(f"  • [{section}] {name}")
            print(f"    └─ {url}\n")
    else:
        print("\n[✓] All tested pages loaded successfully")

    print("\nNote: This is an automated check. Manual review needed to confirm empty pages.")

if __name__ == "__main__":
    main()
