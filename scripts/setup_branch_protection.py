#!/usr/bin/env python3
"""
GitHub Branch Protection Rules Setup
Configures multi-layer protection for all branches via GitHub API
"""

import os
import sys
import requests
import json
from typing import Dict, List, Tuple

# Fix Unicode encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Colors for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

class BranchProtectionSetup:
    def __init__(self, owner: str, repo: str, token: str):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.protected_count = 0
        self.failed_count = 0

    def print_header(self, text: str):
        print(f"\n{YELLOW}{'='*60}")
        print(f"{text}")
        print(f"{'='*60}{NC}\n")

    def print_step(self, text: str):
        print(f"{BLUE}> {text}{NC}")

    def print_success(self, text: str):
        print(f"{GREEN}✓ {text}{NC}")

    def print_error(self, text: str):
        print(f"{RED}✗ {text}{NC}")

    def print_warning(self, text: str):
        print(f"{YELLOW}⚠ {text}{NC}")

    def validate_token(self) -> bool:
        """Validate GitHub token is valid"""
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                user = response.json()
                self.print_success(f"GitHub token valid (user: {user.get('login')})")
                return True
            else:
                self.print_error(f"GitHub token invalid: {response.status_code}")
                return False
        except Exception as e:
            self.print_error(f"Failed to validate token: {str(e)}")
            return False

    def get_protection_config(self, is_main: bool = False) -> Dict:
        """Get branch protection configuration"""
        return {
            "required_status_checks": {
                "strict": True,
                "contexts": ["Code Review Gate - All Branches"]
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "required_approving_review_count": 2 if is_main else 1
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "required_conversation_resolution": True,
            "require_branches_to_be_up_to_date": True
        }

    def protect_branch(self, branch_name: str, is_main: bool = False) -> bool:
        """Apply protection to a single branch"""
        config = self.get_protection_config(is_main=is_main)

        try:
            response = requests.put(
                f"{self.api_url}/branches/{branch_name}/protection",
                headers=self.headers,
                json=config,
                timeout=10
            )

            if response.status_code in [200, 201]:
                self.print_success(f"Branch '{branch_name}' protected")
                self.protected_count += 1
                return True
            elif response.status_code == 404:
                self.print_warning(f"Branch '{branch_name}' not found")
                return False
            else:
                error_msg = response.json().get("message", "Unknown error")
                self.print_error(f"Branch '{branch_name}': {error_msg}")
                self.failed_count += 1
                return False

        except Exception as e:
            self.print_error(f"Failed to protect '{branch_name}': {str(e)}")
            self.failed_count += 1
            return False

    def get_all_branches(self) -> List[str]:
        """Get all branches in the repository"""
        branches = []
        page = 1

        try:
            while True:
                response = requests.get(
                    f"{self.api_url}/branches?per_page=100&page={page}",
                    headers=self.headers,
                    timeout=10
                )

                if response.status_code != 200:
                    self.print_error(f"Failed to fetch branches: {response.status_code}")
                    break

                data = response.json()
                if not data:
                    break

                branches.extend([b["name"] for b in data])
                page += 1

            return branches
        except Exception as e:
            self.print_error(f"Failed to get branches: {str(e)}")
            return []

    def check_workflow(self) -> bool:
        """Check if code-gate workflow exists and is active"""
        try:
            response = requests.get(
                f"{self.api_url}/actions/workflows",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                workflows = response.json()
                for workflow in workflows.get("workflows", []):
                    if "code-gate" in workflow.get("name", ""):
                        if workflow.get("state") == "active":
                            self.print_success(f"GitHub Actions workflow '{workflow['name']}' is active")
                            return True
                        else:
                            self.print_warning(f"Workflow '{workflow['name']}' found but not active")
                            return False

                self.print_warning("code-gate workflow not yet indexed by GitHub (may take a few minutes)")
                return False
            else:
                self.print_warning("Unable to verify workflows")
                return False

        except Exception as e:
            self.print_warning(f"Could not verify workflow: {str(e)}")
            return False

    def run(self):
        """Execute full branch protection setup"""
        self.print_header("GitHub Branch Protection Setup")
        print(f"Repository: {self.owner}/{self.repo}\n")

        # Step 1: Validate token
        self.print_step("Step 1: Validating GitHub token")
        if not self.validate_token():
            self.print_error("Cannot proceed without valid token")
            sys.exit(1)

        # Step 2: Protect main branches
        self.print_step("Step 2: Protecting main branches (strictest settings)")
        main_protected = self.protect_branch("main", is_main=True)
        master_protected = self.protect_branch("master", is_main=True)
        dev_protected = self.protect_branch("develop", is_main=False)

        # Step 3: Get all branches
        self.print_step("Step 3: Fetching all branches")
        all_branches = self.get_all_branches()
        self.print_success(f"Found {len(all_branches)} branches")

        # Step 4: Protect all branches
        self.print_step("Step 4: Applying protection to all branches")
        for branch in all_branches:
            if branch not in ["main", "master", "develop"]:
                self.protect_branch(branch, is_main=False)

        # Step 5: Check workflow
        self.print_step("Step 5: Verifying GitHub Actions workflow")
        self.check_workflow()

        # Summary
        self.print_header("Summary")
        print(f"{GREEN}Protected branches: {self.protected_count}{NC}")
        print(f"{RED}Failed: {self.failed_count}{NC}\n")

        print("Branch Protection Status:")
        print(f"  {GREEN if main_protected else RED}✓ main: {'Protected' if main_protected else 'Failed'}{NC}")
        print(f"  {GREEN if master_protected else RED}✓ master: {'Protected' if master_protected else 'Failed'}{NC}")
        print(f"  {GREEN if dev_protected else RED}✓ develop: {'Protected' if dev_protected else 'Failed'}{NC}\n")

        print(f"{GREEN}Next steps:{NC}")
        print(f"  1. Go to: https://github.com/{self.owner}/{self.repo}/settings/branches")
        print(f"  2. Verify protection rules are applied")
        print(f"  3. Test: Try pushing code with violations (should be blocked)")
        print(f"\n{GREEN}Protection is now LIVE!{NC}\n")


def main():
    """Main entry point"""
    # Get GitHub token
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print(f"{RED}ERROR: GITHUB_TOKEN environment variable not set{NC}")
        print("\nUsage:")
        print("  # Linux/Mac:")
        print("  export GITHUB_TOKEN=your_token")
        print("  python3 scripts/setup_branch_protection.py")
        print("\n  # Windows (PowerShell):")
        print("  $env:GITHUB_TOKEN='your_token'")
        print("  python scripts/setup_branch_protection.py")
        print("\n  # Or use GitHub CLI token:")
        print("  export GITHUB_TOKEN=$(gh auth token)")
        print("  python3 scripts/setup_branch_protection.py")
        sys.exit(1)

    # Run setup
    setup = BranchProtectionSetup(
        owner="rapidtechnologiesllc-byte",
        repo="WROS-Master",
        token=token
    )
    setup.run()


if __name__ == "__main__":
    main()
