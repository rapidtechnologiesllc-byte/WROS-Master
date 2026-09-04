#!/usr/bin/env python3
import logging
"""Comprehensive audit of all syntax and corruption issues in endpoint files."""

import os
import re
import glob

issues = []

for filepath in sorted(glob.glob('app/api/v1/endpoints/*.py')):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        # Check for unquoted dictionary keys: key: value -> should be "key": value
        if re.search(r'\b[a-z_]+:\s*[^"\']', line) and ':' in line and not line.strip().startswith('#'):
            if not re.search(r'"[a-z_]+":', line) and not re.search(r"'[a-z_]+':", line):
                if not re.search(r'http:', line) and not re.search(r'https:', line) and not re.search(r'^\s*#', line):
                    # Skip lines that are comments or URLs
                    if ':' in line and not line.strip().startswith('//') and not line.strip().startswith('*'):
                        if re.search(r'\b[a-z_]{2,}:\s+', line):
                            issues.append((filepath, i, "Unquoted dict key", line.strip()))

        # Check for unquoted f-string or bare variable after f
        if re.search(r'f([A-Z]|[a-z_][a-z_]+\s|[a-z_][a-z_]+\()', line):
            if not re.search(r'f"', line) and not re.search(r"f'", line):
                issues.append((filepath, i, "Unquoted f-string", line.strip()))

        # Check for trailing "or ," pattern
        if re.search(r'\bor\s*,', line):
            issues.append((filepath, i, "Malformed or clause", line.strip()))

        # Check for unquoted values in function calls: key=value
        if re.search(r'\w+=([A-Z][A-Za-z_]*)\s*[,)]', line):
            if not re.search(r'=f"', line) and not re.search(r"=f'", line) and not re.search(r'=\{', line):
                if re.search(r'=([A-Z][a-z_]+)\s*[,)]', line):
                    match = re.search(r'=([A-Z][a-z_]+)\s*([,)])', line)
                    if match and match.group(1) not in ['True', 'False', 'None']:
                        if not line.strip().startswith('from ') and not line.strip().startswith('import '):
                            issues.append((filepath, i, "Unquoted constant", line.strip()))

        # Check for smart quotes
        if '\xe2\x80\x9c' in line or '\xe2\x80\x9d' in line or '“' in line or '”' in line:
            issues.append((filepath, i, "Smart quotes", line.strip()))

print(f"\n{'='*80}")
print(f"CORRUPTION AUDIT REPORT")
print(f"{'='*80}\n")

if issues:
    print(f"Found {len(issues)} potential issues:\n")

    # Group by file
    files_with_issues = {}
    for filepath, line_num, issue_type, line_text in issues:
        if filepath not in files_with_issues:
            files_with_issues[filepath] = []
        files_with_issues[filepath].append((line_num, issue_type, line_text))

    for filepath in sorted(files_with_issues.keys()):
        print(f"\n{filepath}:")
        for line_num, issue_type, line_text in files_with_issues[filepath]:
            print(f"  Line {line_num}: [{issue_type}] {line_text[:80]}")
else:
    print("✅ No corruption detected!")

print(f"\n{'='*80}\n")
