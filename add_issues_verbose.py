#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
import sys

GITHUB_TOKEN = "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"
PROJECT_ID = "PVT_kwHOD2fGNs4BgS1H"
REPO = "rapidtechnologiesllc-byte/WROS-Master"

# Force UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

graphql_headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

# Try to add issue #59
print("Testing with issue #59...")
print("=" * 60)

# Step 1: Get the issue ID
print("\n1. Fetching issue #59 details...")
resp = requests.get(
    f'https://api.github.com/repos/{REPO}/issues/59',
    headers=headers
)
print(f"   Status: {resp.status_code}")

if resp.status_code == 200:
    issue = resp.json()
    issue_id = issue['id']
    print(f"   Issue ID (global): {issue_id}")
    print(f"   Issue number: {issue['number']}")
    print(f"   Title: {issue['title']}")
    
    # Step 2: Try GraphQL mutation with verbose error handling
    print("\n2. Attempting GraphQL mutation to add to project...")
    
    mutation = f"""
    mutation {{
        addProjectV2ItemById(input: {{
            projectId: "{PROJECT_ID}"
            contentId: "{issue_id}"
        }}) {{
            item {{
                id
                type
            }}
            clientMutationId
        }}
    }}
    """
    
    print(f"   Mutation: addProjectV2ItemById")
    print(f"   ProjectId: {PROJECT_ID}")
    print(f"   ContentId: {issue_id}")
    
    resp = requests.post(
        'https://api.github.com/graphql',
        headers=graphql_headers,
        json={'query': mutation},
        timeout=10
    )
    
    print(f"   Response Status: {resp.status_code}")
    
    data = resp.json()
    print(f"   Response: {json.dumps(data, indent=2)}")
    
    if 'errors' in data:
        print(f"\n   ❌ GraphQL Errors:")
        for err in data['errors']:
            print(f"      - {err.get('message', 'Unknown error')}")
            if 'locations' in err:
                print(f"        Location: {err['locations']}")
    elif 'data' in data and data['data']['addProjectV2ItemById']:
        print(f"\n   ✅ Successfully added!")
        print(f"      Item ID: {data['data']['addProjectV2ItemById']['item']['id']}")
    else:
        print(f"\n   ⚠️  No data returned (mutation may have failed)")
else:
    print(f"   Error fetching issue: {resp.status_code}")
    print(f"   {resp.text}")
