#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create 26 GitHub Issues for Orphaned Endpoints
Requires GitHub token with repo + project scopes
"""

import os
import sys
import requests
import json
from typing import List, Tuple

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
REPO_OWNER = 'rapidtechnologiesllc-byte'
REPO_NAME = 'WROS-Master'
PROJECT_ID = 'PVT_kwHOD2fGNs4BgS1H'  # Correct project ID from earlier fix

BASE_URL = 'https://api.github.com'
REPO_URL = f'{BASE_URL}/repos/{REPO_OWNER}/{REPO_NAME}'

# Orphaned endpoint files
ORPHANED_FILES = [
    'agent_config',
    'bi_explorer',
    'bu_head_dashboard',
    'candidate_ranking',
    'candidate_rejection',
    'complete_workflow',
    'conversions',
    'crud',
    'doctor_traces_dashboard',
    'employee_conversion',
    'hiring_manager_validation',
    'interview_decision',
    'invoices_s316',
    'offers',
    'onboarding_orchestrator',
    'onboarding_workflow',
    'queue',
    'queue_dashboard',
    'queues',
    'resume_versions',
    'revenue_recognition',
    'spartan_forecasting',
    'spartan_integration',
    'strategic_consul',
    'system_health',
    'training_dashboards',
]

def create_issue(filename: str) -> Tuple[bool, str, int]:
    """Create a GitHub issue for an orphaned endpoint file."""

    title = f'Backlog: {filename} endpoint - Not registered (orphaned code)'

    body = f"""## Status: Orphaned / Not Registered

**File:** `backend/app/api/v1/endpoints/{filename}.py`

**Issue:** This endpoint file exists in the codebase but is NOT registered in `app/api/v1/routes.py`.

This causes:
- Frontend screens trying to call it get 404 errors
- Dead code that appears complete but doesn't run
- Gate reports false positives for security issues

## Decision Required

**Choose ONE option:**

### Option A: DELETE
Remove the file if it's truly dead code.

```bash
git rm backend/app/api/v1/endpoints/{filename}.py
git commit -m "remove: Delete orphaned endpoint {filename}"
```

### Option B: REGISTER
Register in routes.py if it should be active.

1. Open `backend/app/api/v1/routes.py`
2. Add import: `from app.api.v1.endpoints.{filename} import router as {filename}_router`
3. Add router: `router.include_router({filename}_router)`

### Option C: ARCHIVE
Move to backlog if might need later.

```bash
mkdir -p backend/backlog/endpoints
git mv backend/app/api/v1/endpoints/{filename}.py backend/backlog/endpoints/
```

**Related:** Parent issue tracking all 26 orphaned endpoints
**See:** GATE_ACCURACY_REPORT.md for context
"""

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    data = {
        'title': title,
        'body': body,
        'labels': ['backlog', 'backend', 'cleanup', 'orphaned-code']
    }

    try:
        response = requests.post(
            f'{REPO_URL}/issues',
            headers=headers,
            json=data,
            timeout=10
        )

        if response.status_code == 201:
            issue_data = response.json()
            issue_num = issue_data['number']
            return True, f'Created', issue_num
        else:
            error = response.json().get('message', 'Unknown error')
            return False, f'Error: {error}', 0

    except Exception as e:
        return False, f'Exception: {str(e)}', 0

def add_issue_to_project(issue_number: int) -> bool:
    """Add issue to GitHub project board."""

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    # First, get the issue's global ID
    try:
        response = requests.get(
            f'{REPO_URL}/issues/{issue_number}',
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return False

        issue_id = response.json()['id']

        # Now add to project via GraphQL
        query = f"""
        mutation {{
            addProjectV2ItemById(input: {{
                projectId: "{PROJECT_ID}"
                contentId: "{issue_id}"
            }}) {{
                item {{
                    id
                }}
            }}
        }}
        """

        graphql_response = requests.post(
            'https://api.github.com/graphql',
            headers=headers,
            json={'query': query},
            timeout=10
        )

        if graphql_response.status_code == 200:
            data = graphql_response.json()
            if 'errors' not in data:
                return True

        return False

    except Exception as e:
        print(f'Exception adding to project: {str(e)}')
        return False

def main():
    if not GITHUB_TOKEN:
        print('❌ GITHUB_TOKEN environment variable not set')
        print('Usage: GITHUB_TOKEN=ghp_xxx python create_github_issues.py')
        sys.exit(1)

    print('\n' + '='*60)
    print('Creating GitHub Issues for Orphaned Endpoints')
    print('='*60 + '\n')

    created_issues = []
    failed_issues = []

    for filename in ORPHANED_FILES:
        print(f'Creating issue for {filename}.py... ', end='', flush=True)

        success, message, issue_num = create_issue(filename)

        if success:
            print(f'✅ #{issue_num}')

            # Try to add to project
            print(f'  Adding to project... ', end='', flush=True)
            if add_issue_to_project(issue_num):
                print('✅')
            else:
                print('⚠️  (manual add needed)')

            created_issues.append((filename, issue_num))
        else:
            print(f'❌ {message}')
            failed_issues.append((filename, message))

    print('\n' + '='*60)
    print(f'Created: {len(created_issues)} issues')
    print(f'Failed:  {len(failed_issues)} issues')
    print('='*60 + '\n')

    if created_issues:
        print('✅ Created Issues:')
        for filename, issue_num in created_issues:
            print(f'  #{issue_num}: {filename}')

    if failed_issues:
        print('\n❌ Failed Issues:')
        for filename, error in failed_issues:
            print(f'  {filename}: {error}')

    print('\n' + '='*60)
    print('Next Steps:')
    print(f'  View project: https://github.com/users/{REPO_OWNER}/projects/1')
    print(f'  Issues: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues')
    print('='*60 + '\n')

    return 0 if len(failed_issues) == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
