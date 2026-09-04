#!/usr/bin/env python3
"""Fix files with 'logger = logging.getLogger' but no 'import logging'"""

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
fixed_count = 0

for pyfile in BACKEND_DIR.rglob("*.py"):
    if '__pycache__' in str(pyfile):
        continue

    try:
        with open(pyfile, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue

    # Check if file uses logging.getLogger
    if 'logger = logging.getLogger' not in content:
        continue

    # Check if logging is already imported
    if re.search(r'^\s*import logging\b', content, re.MULTILINE):
        continue

    # Add logging import after other imports
    lines = content.split('\n')
    insert_index = 0

    # Find the line after docstring and before other imports
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines):
        # Skip docstrings
        if line.strip().startswith('"""') or line.strip().startswith("'''"):
            if not in_docstring:
                docstring_char = '"""' if '"""' in line else "'''"
                in_docstring = True
            elif in_docstring and docstring_char in line:
                in_docstring = False
            continue

        if in_docstring:
            continue

        # Skip comments
        if line.strip().startswith('#'):
            continue

        # Found first non-comment, non-docstring line
        if line.strip():
            insert_index = i
            break

    # Insert 'import logging' after existing imports
    for i in range(insert_index, len(lines)):
        line = lines[i]
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            insert_index = i + 1
        elif line.strip() and not line.strip().startswith('import') and not line.strip().startswith('from'):
            break

    # Add logging import if not already there
    if insert_index > 0 and 'import logging' not in '\n'.join(lines[:insert_index+1]):
        lines.insert(insert_index, 'import logging')

        with open(pyfile, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        fixed_count += 1
        print(f"✅ Fixed: {pyfile.relative_to(BACKEND_DIR.parent.parent)}")

print(f"\n✅ Total fixed: {fixed_count} files")
