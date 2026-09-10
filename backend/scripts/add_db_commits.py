#!/usr/bin/env python3
"""Add explicit db.commit() to CRUD endpoints missing it."""
import re
import os
from pathlib import Path

ENDPOINTS_DIR = Path(__file__).parent.parent / "app" / "api" / "v1" / "endpoints"

def add_db_commits_to_file(filepath):
    """Add db.commit() before return statements in CRUD functions."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    original = content

    # Pattern: db.add(...) followed by return without commit
    # Replace with: db.add(...) \n db.commit() \n return

    pattern = r'(db\.add\([^)]+\))\n(\s+)(return )'
    replacement = r'\1\n\2db.commit()\n\2\3'
    content = re.sub(pattern, replacement, content)

    # Pattern: db.query(...).update(...) without commit
    pattern = r'(\.update\([^)]+\))\n(\s+)(return )'
    replacement = r'\1\n\2db.commit()\n\2\3'
    content = re.sub(pattern, replacement, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Find all endpoint files
count = 0
for pyfile in ENDPOINTS_DIR.rglob("*.py"):
    if pyfile.name != "__init__.py":
        if add_db_commits_to_file(pyfile):
            print(f"Updated: {pyfile.relative_to(ENDPOINTS_DIR.parent.parent)}")
            count += 1

print(f"Total files updated: {count}")
