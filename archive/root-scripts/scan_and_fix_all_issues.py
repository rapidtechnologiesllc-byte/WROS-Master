#!/usr/bin/env python3
"""
Scan entire backend for code quality issues and create GitHub issues.
Covers: missing permission checks, error messages, null checks, magic numbers.
"""
import os
import re
import subprocess
import json
from pathlib import Path
from collections import defaultdict

def scan_file(file_path):
    """Scan a file for all code quality issues."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return issues

    for i, line in enumerate(lines, 1):
        # Check for magic numbers (hardcoded constants)
        if re.search(r'=\s*\d{3,}(?!\d)', line) and 'import' not in line:
            if not any(x in line for x in ['PORT', 'DATE', 'VERSION', 'TIMEOUT', 'LIMIT']):
                issues.append({
                    'type': 'MEDIUM',
                    'line': i,
                    'issue': 'Magic number',
                    'pattern': 'MAGIC_NUMBER'
                })

        # Check for missing permission checks
        if 'def ' in line and any(x in line for x in ['create', 'update', 'delete', 'POST', 'PUT', 'DELETE']):
            # Look ahead for permission check
            context = ''.join(lines[max(0, i-1):min(len(lines), i+10)])
            if 'permission' not in context.lower() and 'auth' not in context.lower():
                issues.append({
                    'type': 'CRITICAL',
                    'line': i,
                    'issue': 'Missing permission check',
                    'pattern': 'MISSING_PERMISSION'
                })

        # Check for missing null checks before operations
        if re.search(r'\.get\(|\.query\(', line):
            # Check if there's a null check nearby
            context = ''.join(lines[max(0, i-2):min(len(lines), i+5)])
            if 'if ' not in context and 'assert ' not in context:
                issues.append({
                    'type': 'LOW',
                    'line': i,
                    'issue': 'Potential null dereference',
                    'pattern': 'MISSING_NULL_CHECK'
                })

        # Check for bare except clauses without logging
        if re.search(r'except\s*:', line) or re.search(r'except\s+Exception:', line):
            if i < len(lines) - 1:
                next_line = lines[i]
                if 'logger' not in next_line and 'raise' not in next_line:
                    issues.append({
                        'type': 'HIGH',
                        'line': i,
                        'issue': 'Missing error logging in exception handler',
                        'pattern': 'MISSING_ERROR_LOG'
                    })

    return issues

def main():
    """Scan backend and report issues."""
    backend_dir = r'C:\dev\WROS-Master\backend'

    issue_count = defaultdict(int)
    issue_files = defaultdict(list)
    total_files = 0

    for root, dirs, files in os.walk(backend_dir):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_files += 1

                issues = scan_file(file_path)
                for issue in issues:
                    severity = issue['type']
                    issue_count[severity] += 1
                    rel_path = os.path.relpath(file_path, backend_dir)
                    issue_files[rel_path].append(issue)

    print(f"Scanned {total_files} Python files\n")
    print("Issue Summary:")
    print(f"  🔴 CRITICAL: {issue_count['CRITICAL']}")
    print(f"  🟡 HIGH: {issue_count['HIGH']}")
    print(f"  🟠 MEDIUM: {issue_count['MEDIUM']}")
    print(f"  🟢 LOW: {issue_count['LOW']}")
    print(f"\nTop files with issues:")

    for file_path in sorted(issue_files.keys(), key=lambda x: len(issue_files[x]), reverse=True)[:20]:
        issues = issue_files[file_path]
        critical = len([i for i in issues if i['type'] == 'CRITICAL'])
        high = len([i for i in issues if i['type'] == 'HIGH'])
        print(f"  {file_path}: {critical}C {high}H")

if __name__ == '__main__':
    main()
