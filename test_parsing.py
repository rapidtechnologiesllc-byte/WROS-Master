#!/usr/bin/env python3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import re

with open('scan_output.txt', 'r', encoding='utf-8') as f:
    output = f.read()

lines = output.split('\n')

# Simple parsing: look for .py lines followed by count lines
files_with_issues = []

for i in range(len(lines)-1):
    line = lines[i]
    next_line = lines[i + 1]

    # Look for .py files
    if '.py' in line and 'critical' in next_line:
        # Extract file path
        file_match = re.search(r'([\w/\\]+\.py)', line)

        if file_match:
            file_path = file_match.group(1).replace('\\', '/')

            # Parse full counts
            counts_match = re.match(r'\s*(\d+)\s+critical,\s+(\d+)\s+high,\s+(\d+)\s+medium,\s+(\d+)\s+low', next_line)
            if counts_match:
                counts = {
                    'critical': int(counts_match.group(1)),
                    'high': int(counts_match.group(2)),
                    'medium': int(counts_match.group(3)),
                    'low': int(counts_match.group(4))
                }

                total = sum(counts.values())
                if total > 0:
                    files_with_issues.append(file_path)
                    print(f"{len(files_with_issues):3d}. {file_path}")

print(f"\n✅ Total: {len(files_with_issues)} files with issues")
