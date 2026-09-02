#!/usr/bin/env python3
"""
End-to-End System Test
Tests complete flow: Login -> Navigation -> Permissions -> Resources
import logging
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
logger = logging.getLogger(__name__)

class E2ETest:
    def __init__(self):
        self.results = {"passed": 0, "failed": 0, "tests": []}
        self.tokens = {}

    def log(self, name, status, message=""):
        msg = f"{'PASS' if status else 'FAIL'}: {name}"
        if message:
            msg += f" | {message}"
        print(msg)

        if status:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1

        self.results["tests"].append({"name": name, "passed": status, "message": message})

    def test_login_all_roles(self):
        print("\n=== LOGIN TESTS ===")
        users = [
            ("super_user@test.com", "SuperUser123!", "Super User"),
            ("finance_mgr@test.com", "FinanceMgr123!", "Finance Manager"),
            ("employee@test.com", "Employee123!", "Employee"),
        ]

        for email, password, role in users:
            try:
                resp = requests.post(f"{BASE_URL}/auth/login",
                    json={"email": email, "password": password}, timeout=5)

                if resp.status_code == 200:
                    token = resp.json()["access_token"]
                    self.tokens[role] = token
                    self.log(f"Login {role}", True, f"Token: {token[:30]}...")
                else:
                    self.log(f"Login {role}", False, f"HTTP {resp.status_code}")
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                self.log(f"Login {role}", False, str(e))

    def test_navigation_all_roles(self):
        print("\n=== NAVIGATION TESTS ===")
        expected_modules = {
            "Super User": 10,
            "Finance Manager": 6,
            "Employee": 2,
        }

        for role, expected_count in expected_modules.items():
            if role not in self.tokens:
                continue

            try:
                resp = requests.get(f"{BASE_URL}/hr/me/navigation",
                    headers={"Authorization": f"Bearer {self.tokens[role]}"},
                    timeout=5)

                if resp.status_code == 200:
                    data = resp.json()
                    modules = len(data["groups"])
                    resources = sum(len(g["items"]) for g in data["groups"])

                    if modules == expected_count:
                        self.log(f"Navigation {role}", True,
                            f"{modules} modules, {resources} resources")
                    else:
                        self.log(f"Navigation {role}", False,
                            f"Expected {expected_count} modules, got {modules}")
                else:
                    self.log(f"Navigation {role}", False, f"HTTP {resp.status_code}")
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                self.log(f"Navigation {role}", False, str(e))

    def test_resource_access(self):
        print("\n=== RESOURCE ACCESS TESTS ===")

        if "Super User" not in self.tokens:
            return

        try:
            resp = requests.get(f"{BASE_URL}/hr/me/navigation",
                headers={"Authorization": f"Bearer {self.tokens['Super User']}"},
                timeout=5)

            if resp.status_code == 200:
                data = resp.json()
                all_resources = []
                for group in data["groups"]:
                    for item in group["items"]:
                        all_resources.append(item["key"])

                if len(all_resources) >= 170:
                    self.log("Resource Coverage", True, f"{len(all_resources)} resources available")
                else:
                    self.log("Resource Coverage", False, f"Only {len(all_resources)} resources (expected 170+)")
            else:
                self.log("Resource Coverage", False, f"HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.log("Resource Coverage", False, str(e))

    def test_permission_enforcement(self):
        print("\n=== PERMISSION ENFORCEMENT TESTS ===")

        # Test that Finance Manager doesn't have Recruitment resources
        if "Finance Manager" not in self.tokens:
            return

        try:
            resp = requests.get(f"{BASE_URL}/hr/me/navigation",
                headers={"Authorization": f"Bearer {self.tokens['Finance Manager']}"},
                timeout=5)

            if resp.status_code == 200:
                data = resp.json()
                all_keys = []
                for group in data["groups"]:
                    for item in group["items"]:
                        all_keys.append(item["key"])

                # Finance Manager shouldn't see recruitment resources
                prohibited = ["candidates", "jobs", "interviews", "offers"]
                found_prohibited = [r for r in prohibited if r in all_keys]

                if not found_prohibited:
                    self.log("Permission Enforcement", True,
                        "Finance Manager correctly blocked from recruitment")
                else:
                    self.log("Permission Enforcement", False,
                        f"Finance Manager has access to: {found_prohibited}")
            else:
                self.log("Permission Enforcement", False, f"HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            self.log("Permission Enforcement", False, str(e))

    def print_summary(self):
        print("\n" + "="*60)
        print("END-TO-END TEST SUMMARY")
        print("="*60)
        total = self.results["passed"] + self.results["failed"]
        print(f"Total: {total} | Passed: {self.results['passed']} | Failed: {self.results['failed']}")
        pct = (100 * self.results['passed'] // total) if total > 0 else 0
        print(f"Success Rate: {pct}%")
        print("="*60)

        if self.results["failed"] > 0:
            print("\nFailed Tests:")
            for test in self.results["tests"]:
                if not test["passed"]:
                    print(f"  FAIL: {test['name']}: {test['message']}")

        return self.results["failed"] == 0

def main():
    print("Starting End-to-End System Test")
    print(f"Time: {datetime.now().isoformat()}")

    tester = E2ETest()

    tester.test_login_all_roles()
    tester.test_navigation_all_roles()
    tester.test_resource_access()
    tester.test_permission_enforcement()

    success = tester.print_summary()

    with open("e2e_test_results.json", "w") as f:
        json.dump(tester.results, f, indent=2)

    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
