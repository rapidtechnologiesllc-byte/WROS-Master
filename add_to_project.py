#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
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

# Add issues 59-84 to project
for issue_num in range(59, 85):
    print(f'Adding #{issue_num} to project... ', end='', flush=True)
    
    # Get issue ID
    response = requests.get(
        f'https://api.github.com/repos/{REPO}/issues/{issue_num}',
        headers=headers,
        timeout=10
    )
    
    if response.status_code != 200:
        print('❌ (get issue failed)')
        continue
    
    issue_id = response.json()['id']
    
    # Add to project via GraphQL
    query = f"""
    mutation {{
        addProjectV2ItemById(input: {{
            projectId: "{PROJECT_ID}"
            contentId: "{issue_id}"
        }}) {{
            item {{ id }}
        }}
    }}
    """
    
    graphql_response = requests.post(
        'https://api.github.com/graphql',
        headers=headers,
        json={'query': query},
        timeout=10
    )
    
    if graphql_response.status_code == 200 and 'errors' not in graphql_response.json():
        print('✅')
    else:
        print('⚠️')

print('\nDone!')
