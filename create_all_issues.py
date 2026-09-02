#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive GitHub Issue Creation & Project Board Integration
- Runs full codebase scan
- Creates individual GitHub issues for ALL findings
- Automatically adds each issue to project board
- No manual work required
"""

import os
import sys
import requests
import json
import subprocess
import time
from typing import List, Dict, Tuple

# Force UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
GITHUB_TOKEN = "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"
REPO_OWNER = "rapidtechnologiesllc-byte"
REPO_NAME = "WROS-Master"
PROJECT_ID = "PVT_kwHOD2fGNs4BgS1H"

BASE_URL = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}'

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

# Issue severity mapping
SEVERITY_COLORS = {
    'critical': '🔴 CRITICAL',
    'high': '🟠 HIGH',
    'medium': '🟡 MEDIUM',
    'low': '🟢 LOW'
}

def run_scan() -> List[Dict]:
    """Run codebase scan and parse results."""
    print("\n" + "="*70)
    print("RUNNING CODEBASE SCAN...")
    print("="*70)

    result = subprocess.run(
        [sys.executable, 'backend/scripts/scan_codebase.py'],
        capture_output=True,
        text=True,
        cwd='C:/dev/WROS-Master'
    )

    output = result.stdout

    # Parse scan output to extract files and their issues
    files_with_issues = []
    lines = output.split('\n')
    current_file = None
    current_counts = {}
    issue_details = []

    import re

    for line in lines:
        # Parse file lines like: "🔴 backend\app\api\v1\endpoints\activity_feed.py"
        if line.strip().startswith('🔴') or line.strip().startswith('🟠') or line.strip().startswith('🟡') or line.strip().startswith('🟢'):
            # Save previous file if it has issues
            if current_file and (current_counts.get('critical', 0) or current_counts.get('high', 0) or
                                 current_counts.get('medium', 0) or current_counts.get('low', 0)):
                files_with_issues.append({
                    'file': current_file,
                    'counts': current_counts,
                    'details': issue_details,
                    'severity': 'critical' if current_counts.get('critical', 0) > 0 else
                               'high' if current_counts.get('high', 0) > 0 else
                               'medium' if current_counts.get('medium', 0) > 0 else 'low'
                })

            # Extract file path
            match = re.search(r'(backend\\.*|app\\.*)', line)
            if match:
                current_file = match.group(1)
                current_counts = {}
                issue_details = []

        # Parse issue count lines like "21 CRITICAL issues:"
        elif 'CRITICAL issues' in line or 'HIGH issues' in line or 'MEDIUM issues' in line or 'LOW issues' in line:
            count_match = re.search(r'(\d+)\s+(CRITICAL|HIGH|MEDIUM|LOW)', line)
            if count_match:
                count = int(count_match.group(1))
                level = count_match.group(2).lower()
                current_counts[level] = count

        # Collect issue details
        elif line.strip().startswith('•') and current_file:
            issue_details.append(line.strip())

    # Add last file
    if current_file and (current_counts.get('critical', 0) or current_counts.get('high', 0) or
                         current_counts.get('medium', 0) or current_counts.get('low', 0)):
        files_with_issues.append({
            'file': current_file,
            'counts': current_counts,
            'details': issue_details,
            'severity': 'critical' if current_counts.get('critical', 0) > 0 else
                       'high' if current_counts.get('high', 0) > 0 else
                       'medium' if current_counts.get('medium', 0) > 0 else 'low'
        })

    total_issues = sum(sum(f['counts'].values()) for f in files_with_issues)
    print(f"\n✅ Scan complete! Found {total_issues} total issues in {len(files_with_issues)} files:")

    critical_count = sum(f['counts'].get('critical', 0) for f in files_with_issues)
    high_count = sum(f['counts'].get('high', 0) for f in files_with_issues)
    medium_count = sum(f['counts'].get('medium', 0) for f in files_with_issues)
    low_count = sum(f['counts'].get('low', 0) for f in files_with_issues)

    print(f"   🔴 CRITICAL: {critical_count} issues")
    print(f"   🟠 HIGH: {high_count} issues")
    print(f"   🟡 MEDIUM: {medium_count} issues")
    print(f"   🟢 LOW: {low_count} issues")

    return files_with_issues

def create_issue(file_dict: Dict) -> Tuple[bool, str, int]:
    """Create a GitHub issue for a file with multiple issues."""

    file_path = file_dict['file']
    counts = file_dict['counts']
    severity = file_dict['severity']
    details = file_dict['details']

    # Build counts summary
    counts_text = []
    if counts.get('critical', 0):
        counts_text.append(f"{counts['critical']} CRITICAL")
    if counts.get('high', 0):
        counts_text.append(f"{counts['high']} HIGH")
    if counts.get('medium', 0):
        counts_text.append(f"{counts['medium']} MEDIUM")
    if counts.get('low', 0):
        counts_text.append(f"{counts['low']} LOW")

    counts_summary = ", ".join(counts_text)

    # Build title and description
    title = f"[{counts_summary}] Code quality issues in {file_path.split(chr(92))[-1]}"

    # Build issue details section
    details_section = "\n".join(details[:10])  # Limit to first 10 details
    if len(details) > 10:
        details_section += f"\n... and {len(details) - 10} more issues"

    body = f"""## Issue Summary
Found {len(details)} code quality issues in this file.

## Counts
- 🔴 CRITICAL: {counts.get('critical', 0)}
- 🟠 HIGH: {counts.get('high', 0)}
- 🟡 MEDIUM: {counts.get('medium', 0)}
- 🟢 LOW: {counts.get('low', 0)}

## File
`{file_path}`

## Issues Found
```
{details_section}
```

## Severity
{SEVERITY_COLORS[severity]}

## Action Required
Review and fix code quality issues in this file.

This issue was automatically created by comprehensive codebase scan (2026-09-02).
See GATE_ACCURACY_REPORT.md for full scan details.
"""

    data = {
        'title': title,
        'body': body,
        'labels': ['auto-created', severity, 'code-quality', 'scan']
    }

    try:
        response = requests.post(
            f'{BASE_URL}/issues',
            headers=headers,
            json=data,
            timeout=10
        )

        if response.status_code == 201:
            issue_num = response.json()['number']
            return True, 'Created', issue_num
        else:
            error = response.json().get('message', 'Unknown error')
            return False, f'API Error: {error}', 0

    except Exception as e:
        return False, f'Exception: {str(e)}', 0

def get_issue_graphql_id(issue_number: int) -> str:
    """Get the GraphQL node ID for an issue."""
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
    except Exception as e:
        print(f"   Error fetching GraphQL ID: {e}")

    return None

def add_issue_to_project(issue_number: int) -> bool:
    """Add issue to project board using GraphQL."""

    # Get the GraphQL node ID first
    global_id = get_issue_graphql_id(issue_number)
    if not global_id:
        return False

    # Now add to project
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
            if 'errors' not in data and data['data']['addProjectV2ItemById']:
                return True

    except Exception as e:
        print(f"   Error adding to project: {e}")

    return False

def main():
    """Main workflow: Scan → Create Issues → Add to Project Board"""

    # Step 1: Run scan
    files_with_issues = run_scan()

    total_files = len(files_with_issues)

    print("\n" + "="*70)
    print(f"CREATING {total_files} GITHUB ISSUES & ADDING TO PROJECT BOARD")
    print("="*70)

    created_count = 0
    failed_count = 0
    added_to_project = 0
    failed_project = 0

    # Step 2: Create each issue and add to project
    for idx, file_dict in enumerate(files_with_issues, 1):
        file_path = file_dict['file']
        severity = file_dict['severity']
        counts = file_dict['counts']

        counts_text = f"{counts.get('critical', 0)}C {counts.get('high', 0)}H {counts.get('medium', 0)}M {counts.get('low', 0)}L"

        print(f"\n[{idx}/{total_files}] {file_path.split(chr(92))[-1]} ({counts_text})")
        print(f"  Creating issue... ", end='', flush=True)

        success, message, issue_num = create_issue(file_dict)

        if success:
            print(f"✅ #{issue_num}")
            created_count += 1

            # Add to project board
            print(f"  Adding to project... ", end='', flush=True)

            # Small delay to avoid rate limiting
            time.sleep(0.5)

            if add_issue_to_project(issue_num):
                print(f"✅")
                added_to_project += 1
            else:
                print(f"⚠️  (manual add needed)")
                failed_project += 1
        else:
            print(f"❌ {message}")
            failed_count += 1

        # Rate limiting: GitHub allows 5000 requests/hour
        if idx % 5 == 0:
            print(f"\n  [Rate limiting: pausing 1 second...]")
            time.sleep(1)

    # Summary
    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    print(f"\nFiles Processed:     {total_files}")
    print(f"Issues Created:      {created_count}/{total_files}")
    print(f"Issues Failed:       {failed_count}/{total_files}")
    print(f"Added to Project:    {added_to_project}/{created_count}")
    print(f"Project Add Failed:  {failed_project}/{created_count}")

    if created_count > 0:
        print(f"\n✅ GitHub Issues: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues")
        print(f"✅ Project Board: https://github.com/users/{REPO_OWNER}/projects/1")
        print(f"\nProject will have: {57 + created_count} total issues")
    else:
        print(f"\n⚠️  No issues to create (scan found no problems)")

    return 0 if failed_count == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
