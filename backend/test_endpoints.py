#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:8080"
test_results = []

def test_endpoint(name, method, path, expected_status=200):
    """Test an endpoint and report results"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=5)
        elif method == "POST":
            resp = requests.post(url, json={}, timeout=5)
        else:
            return None
        
        success = resp.status_code in [expected_status, 200, 307]
        result = {
            "name": name,
            "path": path,
            "method": method,
            "status": resp.status_code,
            "success": success
        }
        test_results.append(result)
        return success
    except Exception as e:
        result = {
            "name": name,
            "path": path,
            "method": method,
            "error": str(e),
            "success": False
        }
        test_results.append(result)
        return False

print("Testing WROS Backend Endpoints...")
print("=" * 50)

# Core endpoints
test_endpoint("Health Check", "GET", "/health")
test_endpoint("Root", "GET", "/")
test_endpoint("OpenAPI Docs", "GET", "/docs")

# API endpoints
test_endpoint("App Config", "GET", "/api/v1/config/app-config")

print("\nTest Results:")
print("-" * 50)
passed = sum(1 for r in test_results if r.get("success"))
failed = sum(1 for r in test_results if not r.get("success"))

for result in test_results:
    status = "PASS" if result.get("success") else "FAIL"
    error = result.get("error", "")
    http_status = result.get("status", "N/A")
    print(f"[{status}] {result['name']:30} [HTTP {http_status}]")
    if error:
        print(f"      Error: {error}")

print("-" * 50)
print(f"Passed: {passed}/{len(test_results)}")
print(f"Failed: {failed}/{len(test_results)}")

sys.exit(0 if failed == 0 else 1)
