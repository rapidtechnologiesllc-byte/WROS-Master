#!/usr/bin/env python3
"""
Comprehensive Python syntax validator - scans ALL backend files for errors.
"""

import ast
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
EXCLUDE = {'.venv', '__pycache__', '.git', 'migrations', 'alembic'}

def validate_file(filepath):
    """Validate single Python file for syntax errors."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def main():
    """Scan all Python files in backend directory."""
    errors = []

    for pyfile in BACKEND_DIR.rglob('*.py'):
        # Skip excluded dirs
        if any(exc in pyfile.parts for exc in EXCLUDE):
            continue

        valid, error = validate_file(pyfile)
        if not valid:
            rel_path = pyfile.relative_to(BACKEND_DIR.parent.parent)
            errors.append((str(rel_path), error))

    if errors:
        print(f"\n❌ Found {len(errors)} syntax errors:\n")
        for filepath, error in sorted(errors):
            print(f"  {filepath}")
            print(f"    → {error}\n")
        return 1
    else:
        print("✅ All Python files have valid syntax!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
