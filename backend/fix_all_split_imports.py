#!/usr/bin/env python3
"""
COMPREHENSIVE SPLIT IMPORT FIXER
Finds and fixes ALL split imports in the codebase in one pass.
"""

import sys
import io
import re
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKEND_DIR = Path(__file__).parent

def fix_all_split_imports(filepath):
    """Fix all split imports in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return False

    fixed = False
    i = 0
    result_lines = []

    while i < len(lines):
        line = lines[i]

        # Check if this line ends with "import (" and next line starts with "from"
        if 'import (' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()

            if next_line.startswith('from '):
                # This is a split import - move it before
                # Extract the split import
                split_import_stmt = next_line

                # Add the split import before the current line
                result_lines.append(split_import_stmt + '\n')
                result_lines.append(line)

                # Skip the next line (it's been moved)
                i += 2
                fixed = True
                continue

        result_lines.append(line)
        i += 1

    if fixed:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(result_lines)
            return True
        except:
            return False

    return False

# Scan all Python files
print("\n" + "="*70)
print("COMPREHENSIVE SPLIT IMPORT FIXER")
print("="*70 + "\n")

total_files = 0
fixed_files = 0

for pyfile in sorted(BACKEND_DIR.rglob("*.py")):
    if '__pycache__' in str(pyfile) or '.git' in str(pyfile):
        continue

    total_files += 1
    if fix_all_split_imports(pyfile):
        rel_path = str(pyfile.relative_to(BACKEND_DIR))
        print(f"✓ FIXED: {rel_path}")
        fixed_files += 1

print(f"\n" + "="*70)
print(f"Fixed {fixed_files}/{total_files} files")
print("="*70 + "\n")
