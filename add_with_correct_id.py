#!/usr/bin/env python3
import os
# -*- coding: utf-8 -*-
import requests
import json
import sys

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PROJECT_ID = "PVT_kwHOD2fGNs4BgS1H"
REPO = "rapidtechnologiesllc-byte/WROS-Master"
REPO_OWNER = "rapidtechnologiesllc-byte"

# Force UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

def get_issue_global_id(issue_number):
    """Fetch the correct GraphQL global node ID for an issue."""
    query = f"""
    query {{
        repository(owner: "{REPO_OWNER}", name: "WROS-Master") {{
            issue(number: {issue_number}) {{
                id
                number
                title
            }}
        }}
    }}
    """
    
    resp = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': query},
        timeout=10
    )
    
    if resp.status_code == 200:
        data = resp.json()
        if 'errors' not in data and data['data']['repository']['issue']:
            return data['data']['repository']['issue']['id']
    return None

def add_issue_to_project(issue_number):
    """Add a single issue to the project using correct GraphQL ID."""
    global_id = get_issue_global_id(issue_number)
    if not global_id:
        return False, f"Failed to get GraphQL ID for #{issue_number}"
    
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
    
    resp = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': mutation},
        timeout=10
    )
    
    if resp.status_code == 200:
        data = resp.json()
        if 'errors' in data:
            return False, data['errors'][0].get('message', 'Unknown error')
        elif data['data']['addProjectV2ItemById']:
            return True, f"Added to project (item ID: {data['data']['addProjectV2ItemById']['item']['id'][:20]}...)"
    
    return False, f"HTTP {resp.status_code}"

# Test with first few issues
print("\nAdding orphaned endpoint issues to project...")
print("=" * 60)

added = 0
failed = 0

for issue_num in range(59, 65):  # Test first 6
    print(f"\n#{issue_num}... ", end='', flush=True)
    success, msg = add_issue_to_project(issue_num)
    if success:
        print(f"✅ {msg}")
        added += 1
    else:
        print(f"❌ {msg}")
        failed += 1

print("\n" + "=" * 60)
print(f"Summary: {added} added, {failed} failed")

if added > 0:
    print("\n✅ GraphQL fix working! Can now add remaining 20 issues...")
