#!/usr/bin/env python3
import os
# -*- coding: utf-8 -*-
"""
Add all created GitHub issues to project board in batch
- Handles issues that were created but not added to project
- Retries with better error handling
"""

import requests
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PROJECT_ID = "PVT_kwHOD2fGNs4BgS1H"
REPO_OWNER = "rapidtechnologiesllc-byte"
REPO_NAME = "WROS-Master"

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
}

import time

def get_issue_graphql_id(issue_number: int):
    """Get GraphQL node ID for an issue."""
    query = f"""
    query {{
        repository(owner: "{REPO_OWNER}", name: "{REPO_NAME}") {{
            issue(number: {issue_number}) {{
                id
            }}
        }}
    }}
    """

    try:
        response = requests.post(
            'https://api.github.com/graphql',
            headers=headers,
            json={'query': query},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if 'errors' not in data and data['data']['repository']['issue']:
                return data['data']['repository']['issue']['id']
    except:
        pass

    return None

def add_issue_to_project(issue_number: int):
    """Add issue to project board."""

    global_id = get_issue_graphql_id(issue_number)
    if not global_id:
        return False, "Failed to get GraphQL ID"

    mutation = f"""
    mutation {{
        addProjectV2ItemById(input: {{
            projectId: "{PROJECT_ID}"
            contentId: "{global_id}"
        }}) {{
            item {{
                id
            }}
        }}
    }}
    """

    try:
        response = requests.post(
            'https://api.github.com/graphql',
            headers=headers,
            json={'query': mutation},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if 'errors' in data:
                return False, data['errors'][0].get('message', 'GraphQL error')
            if data['data']['addProjectV2ItemById']:
                return True, "Added"

        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    print("\n" + "="*70)
    print("ADDING ALL CREATED ISSUES TO PROJECT BOARD")
    print("="*70)

    # Get last issue number
    last_issue_response = requests.get(
        f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state=all&per_page=1&sort=created&direction=desc',
        headers=headers
    )

    if last_issue_response.status_code != 200:
        print("❌ Failed to get issue list")
        return 1

    last_issue_num = last_issue_response.json()[0]['number']
    print(f"\nLatest issue number: {last_issue_num}")

    # Start from issue #85 (first auto-created)
    start_issue = 85

    if last_issue_num < start_issue:
        print("⚠️  No auto-created issues found")
        return 0

    issues_to_add = list(range(start_issue, last_issue_num + 1))
    total = len(issues_to_add)

    print(f"Will attempt to add {total} issues (#85-#{last_issue_num})\n")

    added = 0
    failed = 0

    for idx, issue_num in enumerate(issues_to_add, 1):
        print(f"[{idx:3d}/{total}] Issue #{issue_num}... ", end='', flush=True)

        success, msg = add_issue_to_project(issue_num)

        if success:
            print(f"✅")
            added += 1
        else:
            print(f"❌ ({msg[:40]})")
            failed += 1

        # Rate limiting
        if idx % 10 == 0:
            print(f"        [Rate limiting: pausing 2 seconds...]")
            time.sleep(2)
        else:
            time.sleep(0.3)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nIssues added:   {added}/{total}")
    print(f"Issues failed:  {failed}/{total}")
    print(f"\nProject: https://github.com/users/{REPO_OWNER}/projects/1")
    print(f"Issues: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
