#!/usr/bin/env python3
import os
# -*- coding: utf-8 -*-
import requests
import sys

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
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

# Try REST API endpoint for adding to project (if it exists)
print("Testing REST API endpoint for adding issues to project...")
print("=" * 60)

# GitHub's REST API endpoint for project v2 items
# Format: POST /repos/{owner}/{repo}/projects/{project_id}/issues/{issue_number}

for issue_num in [59, 60]:
    print(f"\n#{issue_num}...")
    
    # Try different endpoint patterns
    endpoints = [
        # ProjectV2 REST endpoint (newer)
        f'https://api.github.com/repos/{REPO}/issues/{issue_num}/projects',
        # Legacy projects endpoint
        f'https://api.github.com/projects/{PROJECT_ID}/cards',
    ]
    
    for endpoint in endpoints:
        print(f"  Trying: {endpoint}")
        
        resp = requests.post(
            endpoint,
            headers=headers,
            json={'project_id': PROJECT_ID, 'content_id': issue_num},
            timeout=10
        )
        
        print(f"    Status: {resp.status_code}")
        if resp.status_code not in [200, 201, 204]:
            print(f"    Response: {resp.text[:150]}")
