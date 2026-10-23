#!/usr/bin/env python3
"""
Comprehensive WROS Page Data Audit
Tests each menu page's API endpoints to identify pages with no data
"""

import requests
import json
from typing import Dict, List, Tuple
from datetime import datetime

# Configuration
BACKEND_API = "http://localhost:8080"
BASE_URL = "http://localhost:3000"

# Correct test credentials based on the JWT fix notes
TEST_EMAIL = "recruiter@test.com"
TEST_PASSWORD = "TestRecruiter@123"

def login_and_get_token() -> str:
    """
    Login to get JWT token
    Based on CLAUDE.md: JWT token fix verified working
    """
    print("[*] Attempting login with recruiter@test.com...")

    login_url = f"{BACKEND_API}/auth/login"
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }

    try:
        response = requests.post(login_url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token") or data.get("token")
            if token:
                print(f"[✓] Login successful")
                return token
            else:
                print(f"[✗] No token in response: {data.keys()}")
                return None
        else:
            print(f"[✗] Login failed with status {response.status_code}")
            if response.text:
                try:
                    print(f"    Response: {response.json()}")
                except:
                    print(f"    Response: {response.text[:200]}")
            return None

    except Exception as e:
        print(f"[✗] Login exception: {e}")
        return None

def make_api_request(endpoint: str, token: str = None, method: str = "GET") -> Tuple[int, Dict]:
    """
    Make API request and return status + data
    """
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{BACKEND_API}{endpoint}"

        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        else:
            response = requests.post(url, headers=headers, timeout=5)

        status = response.status_code

        try:
            data = response.json()
        except:
            data = {"raw": response.text[:100]}

        return (status, data)

    except Exception as e:
        return (0, {"error": str(e)})

def count_data_items(response_data: Dict) -> int:
    """
    Count how many data items are in response
    Returns 0 if no data
    """
    if not response_data:
        return 0

    # Common data field names
    data_fields = ["data", "items", "results", "candidates", "jobs", "users", "invoices", "projects", "employees"]

    for field in data_fields:
        if field in response_data:
            items = response_data[field]
            if isinstance(items, list):
                return len(items)
            elif isinstance(items, dict) and len(items) > 0:
                return 1

    # Check if response itself is a list
    if isinstance(response_data, list):
        return len(response_data)

    # Check top-level count fields
    for key in ["count", "total", "total_items"]:
        if key in response_data and isinstance(response_data[key], int):
            return response_data[key]

    return 0

# Page to API endpoint mapping
PAGES = {
    "RECRUITMENT": {
        "Candidates": {
            "url": "/candidates",
            "api_endpoints": [
                ("/api/v1/candidates", "List Candidates"),
                ("/api/v1/onboarding/hr/get_all_candidates", "Get All Candidates"),
            ]
        },
        "Jobs": {
            "url": "/jobs",
            "api_endpoints": [
                ("/api/v1/jobs/all", "All Jobs"),
                ("/api/v1/jobs", "Jobs List"),
            ]
        },
        "Submissions": {
            "url": "/submissions",
            "api_endpoints": [
                ("/api/v1/submissions", "Submissions List"),
            ]
        },
        "Interviews": {
            "url": "/interviews",
            "api_endpoints": [
                ("/api/v1/interviews", "Interviews List"),
            ]
        },
        "Offer Letters": {
            "url": "/offer-letters",
            "api_endpoints": [
                ("/api/v1/offers", "Offers List"),
                ("/api/v1/offer_letters", "Offer Letters"),
            ]
        },
        "Intervention Queue": {
            "url": "/intervention-queue",
            "api_endpoints": [
                ("/api/v1/intervention-queue", "Intervention Queue"),
            ]
        },
        "Risk Dashboard": {
            "url": "/risk-dashboard",
            "api_endpoints": [
                ("/api/v1/risk-dashboard", "Risk Dashboard"),
            ]
        },
        "Thunder Analytics": {
            "url": "/thunder-analytics",
            "api_endpoints": [
                ("/api/v1/thunder", "Thunder Analytics"),
            ]
        },
    },
    "WORKFORCE": {
        "Employees": {
            "url": "/employees",
            "api_endpoints": [
                ("/api/v1/employees", "Employees List"),
            ]
        },
        "Allocations": {
            "url": "/allocations",
            "api_endpoints": [
                ("/api/v1/allocations", "Allocations List"),
            ]
        },
    },
    "EXECUTIVE": {
        "CEO Dashboard": {
            "url": "/ceo-dashboard",
            "api_endpoints": [
                ("/api/v1/executive-dashboard", "Executive Dashboard"),
                ("/api/v1/revenue/executive-dashboard", "Revenue Executive Dashboard"),
                ("/api/v1/candidates", "Candidates for Pipeline"),
                ("/api/v1/jobs/all", "Jobs for Pipeline"),
            ]
        },
        "CFO Dashboard": {
            "url": "/cfo-dashboard",
            "api_endpoints": [
                ("/api/v1/cfo-dashboard", "CFO Dashboard"),
            ]
        },
        "Partner Dashboard": {
            "url": "/partner-dashboard",
            "api_endpoints": [
                ("/api/v1/partner-dashboard", "Partner Dashboard"),
            ]
        },
        "Executive Signal": {
            "url": "/executive-signal",
            "api_endpoints": [
                ("/api/v1/executive-signal", "Executive Signal"),
            ]
        },
    },
    "FINANCE": {
        "Invoices": {
            "url": "/invoices",
            "api_endpoints": [
                ("/api/v1/invoices", "Invoices List"),
            ]
        },
        "Reports": {
            "url": "/reports",
            "api_endpoints": [
                ("/api/v1/reports", "Reports List"),
            ]
        },
    },
    "ADMIN": {
        "Users & Access Control": {
            "url": "/users",
            "api_endpoints": [
                ("/api/v1/users", "Users List"),
                ("/api/v1/hr/users/all", "All HR Users"),
            ]
        },
        "Role Templates": {
            "url": "/role-templates",
            "api_endpoints": [
                ("/api/v1/role-templates", "Role Templates"),
            ]
        },
    },
}

def main():
    print("=" * 90)
    print("WROS COMPREHENSIVE PAGE DATA AUDIT")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    # Step 1: Login
    token = login_and_get_token()
    if not token:
        print("\n[!] Could not authenticate. Results may be incomplete.")
        print("    Attempting to test without authentication...\n")

    # Step 2: Test each page's API endpoints
    print("\n" + "=" * 90)
    print("PAGE DATA AUDIT")
    print("=" * 90)

    pages_with_no_data = []
    pages_with_data = []
    pages_with_errors = []

    for section, pages in PAGES.items():
        print(f"\n[{section}]")
        print("-" * 90)

        for page_name, page_info in pages.items():
            page_url = page_info["url"]
            api_endpoints = page_info["api_endpoints"]

            print(f"\n  ► {page_name} ({page_url})")

            has_data = False
            all_failed = True
            total_items = 0

            for endpoint, endpoint_name in api_endpoints:
                status, data = make_api_request(endpoint, token)

                if status < 400:
                    all_failed = False
                    item_count = count_data_items(data)
                    total_items = max(total_items, item_count)

                    if item_count > 0:
                        has_data = True
                        print(f"      ✓ {endpoint_name:40} {status:3} | {item_count:5} items")
                    else:
                        print(f"      • {endpoint_name:40} {status:3} | NO DATA")
                else:
                    print(f"      ✗ {endpoint_name:40} {status:3} | Error")

            # Categorize page
            if all_failed:
                pages_with_errors.append((section, page_name, page_url))
                print(f"    → RESULT: ALL ENDPOINTS FAILED")
            elif has_data:
                pages_with_data.append((section, page_name, page_url, total_items))
                print(f"    → RESULT: HAS DATA ({total_items} items)")
            else:
                pages_with_no_data.append((section, page_name, page_url))
                print(f"    → RESULT: LOADS BUT NO DATA")

    # Step 3: Print Summary
    print("\n" + "=" * 90)
    print("SUMMARY REPORT")
    print("=" * 90)

    print(f"\n✓ PAGES WITH DATA: {len(pages_with_data)}")
    for section, name, url, count in pages_with_data:
        print(f"  • [{section}] {name} ({count} items)")

    print(f"\n✗ PAGES WITH NO DATA (LOADS BUT EMPTY): {len(pages_with_no_data)}")
    if pages_with_no_data:
        for section, name, url in pages_with_no_data:
            print(f"  • [{section}] {name}")
            print(f"    URL: {BASE_URL}{url}")
    else:
        print("  None detected!")

    print(f"\n⚠ PAGES WITH ERRORS (ENDPOINTS FAILED): {len(pages_with_errors)}")
    if pages_with_errors:
        for section, name, url in pages_with_errors:
            print(f"  • [{section}] {name}")
    else:
        print("  None detected!")

    # Critical finding
    print("\n" + "=" * 90)
    print("CRITICAL FINDINGS")
    print("=" * 90)

    if pages_with_no_data:
        print(f"\n[!] {len(pages_with_no_data)} PAGES LOAD BUT SHOW NO DATA:")
        print("    These pages render UI but have zero content from backend.\n")
        for section, name, url in pages_with_no_data:
            print(f"    Issue: {section} > {name}")
            print(f"    Page: {BASE_URL}{url}\n")

        print("    RECOMMENDED ACTIONS:")
        print("    1. Check if API endpoints are returning empty arrays/null")
        print("    2. Verify backend data exists in database")
        print("    3. Check user permissions to access data")
        print("    4. Review frontend API endpoint mappings")
    else:
        print("\n[✓] No critical 'no data' pages found.")

    print("\n" + "=" * 90)

if __name__ == "__main__":
    main()
