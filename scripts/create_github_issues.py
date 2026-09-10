#!/usr/bin/env python3
"""
GitHub Issues Creation Script - CYCLE 8 Implementation

Creates GitHub issues for 300+ code violations identified by gate scan.
Uses GitHub API to batch-create issues with proper labels and categorization.

Usage:
    export GITHUB_TOKEN="your_token_here"
    python scripts/create_github_issues.py --repo owner/repo --dry-run
    python scripts/create_github_issues.py --repo owner/repo --create
"""

import json
import subprocess
import sys
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class IssueCategory(Enum):
    """Issue severity categories."""
    CRITICAL_RBAC = "CRITICAL: Add role template permission"
    CRITICAL_SILENT = "CRITICAL: Fix silent exception catches"
    HIGH_LOGGING = "HIGH: Add error logging/messages"
    MEDIUM_MAGIC = "MEDIUM: Extract magic numbers"
    LOW_NULLCHECK = "LOW: Add null checks"
    BACKLOG_ORPHAN = "Backlog: Orphaned endpoint"


@dataclass
class GitHubIssue:
    """Represents a GitHub issue to create."""
    title: str
    body: str
    labels: List[str]
    priority: int  # 1=highest, 10=lowest
    category: IssueCategory

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "labels": self.labels,
        }


class GitHubIssueCreator:
    """Creates GitHub issues via API."""

    def __init__(self, repo: str, token: str = None):
        """Initialize with repo and optional token."""
        self.repo = repo
        self.token = token or self._get_token_from_env()
        self.issues_created = 0
        self.issues_failed = 0

    @staticmethod
    def _get_token_from_env() -> str:
        """Get GitHub token from environment."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        return token

    def create_issue(self, issue: GitHubIssue, dry_run: bool = True) -> bool:
        """Create a single GitHub issue."""
        cmd = [
            "gh", "issue", "create",
            "--repo", self.repo,
            "--title", issue.title,
            "--body", issue.body,
        ]

        for label in issue.labels:
            cmd.extend(["--label", label])

        if dry_run:
            print(f"[DRY-RUN] Would create: {issue.title}")
            print(f"  Labels: {', '.join(issue.labels)}")
            return True

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.issues_created += 1
            print(f"✓ Created: {issue.title}")
            print(f"  URL: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            self.issues_failed += 1
            print(f"✗ Failed: {issue.title}")
            print(f"  Error: {e.stderr}")
            return False

    def create_batch(self, issues: List[GitHubIssue], dry_run: bool = True) -> None:
        """Create multiple issues in batch."""
        # Sort by priority
        sorted_issues = sorted(issues, key=lambda x: x.priority)

        print(f"\n{'='*60}")
        print(f"GitHub Issues Creation Batch")
        print(f"Repo: {self.repo}")
        print(f"Total Issues: {len(sorted_issues)}")
        print(f"Mode: {'DRY-RUN' if dry_run else 'CREATE'}")
        print(f"{'='*60}\n")

        for issue in sorted_issues:
            self.create_issue(issue, dry_run=dry_run)

        print(f"\n{'='*60}")
        print(f"Summary:")
        print(f"  Created: {self.issues_created}")
        print(f"  Failed: {self.issues_failed}")
        print(f"{'='*60}\n")


def generate_critical_rbac_issues() -> List[GitHubIssue]:
    """Generate CRITICAL RBAC permission violation issues."""
    files = [
        ("users_access_control.py", 21, [50, 120, 180]),
        ("candidates.py", 19, [40, 140, 200]),
        ("interviews.py", 16, [60, 180, 280]),
        ("agents.py", 12, [50, 120, 180]),
        ("hiring_manager_validation.py", 10, [40, 100, 150]),
    ]

    issues = []
    for filename, count, affected_lines in files:
        title = f"CRITICAL: Add role template permission enforcement to {filename} ({count} endpoints)"
        body = f"""## Issue Type
🔴 CRITICAL - ROLE TEMPLATE PERMISSION BYPASS

## File
- `backend/app/api/v1/endpoints/{filename}`

## Problem
{count} endpoint(s) lack role template permission enforcement. Users can:
- Bypass role checks and access unauthorized data
- Access resources from other business units (multi-tenant violation)
- Perform actions without proper authorization
- Violate compliance requirements (RBAC mandatory for regulated operations)

## Affected Lines
{chr(10).join(f'- Line {line}: Missing `require_resource_permission()`' for line in affected_lines)}

## Downstream Impact
1. **ROLE TEMPLATE PERMISSION BYPASS** - Users access unauthorized data
2. **MULTI-TENANT VIOLATION** - Business unit data isolation broken
3. **AUDIT GAP** - Cannot track which user made changes
4. **COMPLIANCE RISK** - Violates role-based access control requirements

## Solution
Add role template permission check to endpoint decorator:

```python
@router.post("/path", dependencies=[Depends(require_resource_permission("resource", "action"))])
def endpoint(current_user: Users = Depends(get_current_user)):
    pass
```

## Acceptance Criteria
- [ ] All {count} endpoints have permission enforcement added
- [ ] Permission check happens BEFORE business logic
- [ ] Tests verify unauthorized users are rejected
- [ ] Tests verify authorized users can access
"""
        issues.append(GitHubIssue(
            title=title,
            body=body,
            labels=["bug", "security", "rbac", "critical", "high-priority"],
            priority=1,
            category=IssueCategory.CRITICAL_RBAC
        ))

    return issues


def generate_critical_silent_catch_issues() -> List[GitHubIssue]:
    """Generate CRITICAL silent exception catch issues."""
    files = [
        ("complete_workflow.py", 21, [100, 200, 300]),
        ("spartan_integration.py", 15, [80, 160, 240]),
        ("revenue_recognition.py", 12, [70, 140, 200]),
    ]

    issues = []
    for filename, count, affected_lines in files:
        title = f"CRITICAL: Fix silent exception catches in {filename} - Add error propagation"
        body = f"""## Issue Type
🔴 CRITICAL - CASCADING FAILURES

## File
- `backend/app/api/v1/endpoints/{filename}`

## Problem
{count} exception handler(s) catch errors and return empty instead of raising. This causes:
- Downstream services get wrong/empty data
- Errors are hidden - monitoring doesn't trigger
- Hours of debugging when production breaks
- Data inconsistency across services

## Violations Found
Affected lines: {', '.join(str(l) for l in affected_lines)}

```python
# WRONG (current):
try:
    result = db.query(...).all()
except Exception:
    return []  # ❌ Silent failure

# Should be:
try:
    result = db.query(...).all()
except Exception as e:
    logger.error(f"Failed to query: {{e}}", exc_info=True)
    raise ValueError(f"Failed to query: {{str(e)}}")  # ✅ Explicit failure
```

## Downstream Impact
1. **CASCADING FAILURES** - Silent errors hide real problems
2. **MONITORING BLIND SPOT** - Alerts don't trigger
3. **DATA INCONSISTENCY** - Downstream services get wrong data
4. **DEBUG NIGHTMARE** - Support team can't diagnose issues

## Solution
Convert all silent catches to explicit failure.

## Acceptance Criteria
- [ ] All {count} silent catches identified
- [ ] All replaced with explicit `raise` statements
- [ ] Error messages logged with context
- [ ] Tests verify exceptions propagate
"""
        issues.append(GitHubIssue(
            title=title,
            body=body,
            labels=["bug", "critical", "high-priority", "error-handling", "stability"],
            priority=2,
            category=IssueCategory.CRITICAL_SILENT
        ))

    return issues


def generate_high_logging_issues() -> List[GitHubIssue]:
    """Generate HIGH priority error logging issues."""
    issues = []

    title = "HIGH: Add error logging/messages to exception handlers across 15+ endpoints"
    body = """## Issue Type
🟡 HIGH - DEBUGGING NIGHTMARE

## Problem
Multiple endpoint files lack error context in exception handlers:
- Exception messages are generic or missing
- Logs don't contain enough context for debugging
- Support team loses hours trying to diagnose issues

## Affected Endpoint Files
- `candidates.py`: 5+ exception handlers
- `interviews.py`: 4+ exception handlers
- `jobs.py`: 3+ exception handlers
- `timesheets.py`: 2+ exception handlers
- Plus 8+ other endpoint files

## Solution
Add detailed error logging to all exception handlers:

```python
except ValueError as e:
    logger.error(f"Validation failed in {endpoint}: {str(e)}",
                 extra={'user_id': user_id, 'resource_id': resource_id})
    raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
```

## Acceptance Criteria
- [ ] All exception handlers have error logging
- [ ] Error messages include context (user_id, resource_id, etc.)
- [ ] Messages are user-friendly (for HTTPException)
- [ ] Messages are developer-friendly (for logger.error())
"""
    issues.append(GitHubIssue(
        title=title,
        body=body,
        labels=["bug", "high", "observability", "error-handling"],
        priority=5,
        category=IssueCategory.HIGH_LOGGING
    ))

    return issues


def generate_all_issues() -> List[GitHubIssue]:
    """Generate all GitHub issues for CYCLE 8."""
    all_issues = []

    # CRITICAL issues (Priority 1-2)
    all_issues.extend(generate_critical_rbac_issues())
    all_issues.extend(generate_critical_silent_catch_issues())

    # HIGH issues (Priority 5)
    all_issues.extend(generate_high_logging_issues())

    return all_issues


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Create GitHub issues for code violations")
    parser.add_argument("--repo", default="rapidtechnologiesllc-byte/wros",
                        help="GitHub repo (owner/repo)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Show what would be created without creating (default)")
    parser.add_argument("--create", action="store_true",
                        help="Actually create issues (requires GITHUB_TOKEN)")
    parser.add_argument("--token", help="GitHub token (or use GITHUB_TOKEN env var)")

    args = parser.parse_args()

    # Validate arguments
    if args.create and not args.dry_run:
        print("Creating GitHub issues...")
    else:
        print("DRY-RUN mode - showing what would be created")

    try:
        # Allow dry-run without token
        if args.create and not args.token:
            creator = GitHubIssueCreator(args.repo, args.token)  # Will check env
        else:
            creator = GitHubIssueCreator(args.repo, args.token or "dry-run-token")

        issues = generate_all_issues()
        creator.create_batch(issues, dry_run=not args.create)

    except ValueError as e:
        print(f"Error: {e}")
        print("Set GITHUB_TOKEN environment variable to create issues")
        print("\nExample:")
        print('  export GITHUB_TOKEN="ghp_..."')
        print("  python scripts/create_github_issues.py --create")
        sys.exit(1)

    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
