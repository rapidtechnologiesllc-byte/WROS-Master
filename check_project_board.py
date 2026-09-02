#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import sys

GITHUB_TOKEN = "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"
PROJECT_ID = "PVT_kwHOD2fGNs4BgS1H"

# Force UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

# Query project to see how many items it has
query = f"""
query {{
    node(id: "{PROJECT_ID}") {{
        ... on ProjectV2 {{
            title
            items(first: 100) {{
                totalCount
                edges {{
                    node {{
                        id
                        content {{
                            ... on Issue {{
                                number
                                title
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
}}
"""

response = requests.post(
    'https://api.github.com/graphql',
    headers=headers,
    json={'query': query},
    timeout=10
)

if response.status_code == 200:
    data = response.json()
    if 'data' in data and data['data']['node']:
        project = data['data']['node']
        print(f"Project: {project['title']}")
        print(f"Total Items: {project['items']['totalCount']}")
        print(f"\nIssues in project:")
        
        issue_numbers = []
        for edge in project['items']['edges']:
            if edge['node']['content']:
                issue_num = edge['node']['content'].get('number')
                title = edge['node']['content'].get('title', 'Unknown')
                print(f"  #{issue_num}: {title[:60]}")
                issue_numbers.append(issue_num)
        
        # Check if 59-84 are in the project
        orphaned_issues = set(range(59, 85))
        found_issues = set(n for n in issue_numbers if n and 59 <= n <= 84)
        
        print(f"\nOrphaned endpoint issues check:")
        print(f"  Expected (#59-#84): {len(orphaned_issues)} issues")
        print(f"  Found in project: {len(found_issues)} issues")
        
        if found_issues:
            print(f"  ✅ Issues {min(found_issues)}-{max(found_issues)} are in project")
        else:
            print(f"  ❌ No orphaned endpoint issues found (need manual add)")
    else:
        print(f"Error: {data}")
else:
    print(f"HTTP {response.status_code}: {response.text}")
