#!/usr/bin/env python3
"""Bulk fix all common import errors"""

import re
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).parent

# Common undefined names and their fixes
FIXES = {
    'Depends': 'from fastapi import Depends',
    'HTTPException': 'from fastapi import HTTPException',
    'APIRouter': 'from fastapi import APIRouter',
    'Request': 'from fastapi import Request',
    'BackgroundTasks': 'from fastapi import BackgroundTasks',
    'get_current_internal_user': 'from app.core.dependencies import get_current_internal_user',
    'get_current_candidate': 'from app.core.dependencies import get_current_candidate',
    'get_db': 'from app.core.database import get_db',
    'Session': 'from sqlalchemy.orm import Session',
    'logger': 'from app.core.logging import logger',
    'logging': 'import logging',
}

fixed_count = 0

def add_import_to_file(filepath, import_stmt):
    """Add import statement to file after existing imports"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already imported
    if import_stmt in content:
        return False

    lines = content.split('\n')
    insert_pos = 0
    in_docstring = False

    # Find insertion point after docstring and imports
    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            in_docstring = not in_docstring
            continue

        if in_docstring:
            continue

        # Skip comments and blank lines
        if stripped.startswith('#') or not stripped:
            continue

        # Track imports
        if stripped.startswith('import ') or stripped.startswith('from '):
            insert_pos = i + 1
            continue

        # First non-import, non-comment line
        if stripped and not stripped.startswith('import') and not stripped.startswith('from'):
            break

    lines.insert(insert_pos, import_stmt)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return True

def find_and_fix_file(filepath):
    """Try to import the file and identify/fix missing names"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Quick check for undefined names we know about
        for name, import_stmt in FIXES.items():
            # Check if name is used but not imported
            if re.search(r'\b' + re.escape(name) + r'\b', content):
                if import_stmt not in content:
                    # Check basic patterns to avoid false positives
                    if name in ('Depends', 'HTTPException', 'APIRouter', 'Request', 'BackgroundTasks'):
                        # These are FastAPI imports - usually in decorator arguments
                        if f'from fastapi import' in content and name not in content.split('from fastapi import')[1].split('\n')[0]:
                            add_import_to_file(filepath, import_stmt)
                            return True
                    elif name in FIXES:
                        add_import_to_file(filepath, import_stmt)
                        return True

    except Exception:
        pass

    return False

# Scan all Python files in endpoints, services, schemas
for pattern in ['app/api/v1/endpoints/*.py', 'app/services/*.py', 'app/schemas/*.py']:
    for pyfile in BACKEND_DIR.glob(pattern):
        if find_and_fix_file(pyfile):
            rel_path = pyfile.relative_to(BACKEND_DIR.parent.parent)
            print(f"✅ Fixed: {rel_path}")
            fixed_count += 1

print(f"\n✅ Total files fixed: {fixed_count}")
