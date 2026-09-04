#!/usr/bin/env python3
"""
Iteratively fix import errors and start the server

This script attempts to import app.main, catches NameError exceptions from
missing imports, adds those imports, and retries until successful.
"""

import re
import sys
import traceback
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR.parent))

# Common import patterns to try
COMMON_IMPORTS = {
    'Depends': 'from fastapi import Depends',
    'HTTPException': 'from fastapi import HTTPException',
    'APIRouter': 'from fastapi import APIRouter',
    'Session': 'from sqlalchemy.orm import Session',
    'Optional': 'from typing import Optional',
    'List': 'from typing import List',
    'Dict': 'from typing import Dict',
    'Tuple': 'from typing import Tuple',
    'Any': 'from typing import Any',
    'Union': 'from typing import Union',
    'logging': 'import logging',
    'os': 'import os',
    'json': 'import json',
    'datetime': 'from datetime import datetime',
    'date': 'from datetime import date',
    'timedelta': 'from datetime import timedelta',
    'require_resource_permission': 'from app.core.dependencies import require_resource_permission',
    'require_permission': 'from app.core.dependencies import require_permission',
    'get_db': 'from app.core.database import get_db',
    'logger': 'from app.core.logging import logger',
    'BaseModel': 'from pydantic import BaseModel',
    're': 'import re',
}

attempt = 0
max_attempts = 20
last_error = None

while attempt < max_attempts:
    attempt += 1
    print(f"\n[Attempt {attempt}] Loading app.main...")

    try:
        # Clear any cached imports
        if 'app' in sys.modules:
            # Remove all app.* modules from cache
            keys_to_remove = [k for k in sys.modules if k.startswith('app.')]
            for k in keys_to_remove:
                del sys.modules[k]

        # Try to import
        import app.main
        print("✅ SUCCESS! app.main loaded without errors.")
        print("\nAttempting to start server...")

        # If we got here, imports succeeded - start the server
        import uvicorn
        uvicorn.run(
            app.main.app,
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_level="info"
        )
        break

    except NameError as e:
        last_error = e
        error_msg = str(e)

        # Extract undefined name
        if "name '" in error_msg:
            undefined_name = error_msg.split("name '")[1].split("'")[0]
            print(f"❌ NameError: '{undefined_name}' is not defined")

            # Get traceback to find the file
            tb_str = traceback.format_exc()
            # Extract filename from traceback
            file_match = re.search(r'File "([^"]+)", line (\d+)', tb_str)
            if file_match:
                problem_file = file_match.group(1)
                problem_line = int(file_match.group(2))
                print(f"   In: {problem_file}:{problem_line}")

                # Try to fix the file
                if problem_file.endswith('.py'):
                    try:
                        filepath = Path(problem_file)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Check if name is already used
                        if undefined_name in content:
                            # Try to add import
                            import_stmt = COMMON_IMPORTS.get(undefined_name)
                            if import_stmt:
                                if import_stmt not in content:
                                    print(f"   Adding: {import_stmt}")
                                    # Add import after docstring and existing imports
                                    lines = content.split('\n')
                                    insert_pos = 0
                                    in_docstring = False

                                    for i, line in enumerate(lines):
                                        if '"""' in line or "'''" in line:
                                            in_docstring = not in_docstring
                                        if not in_docstring and (line.startswith('import ') or line.startswith('from ')):
                                            insert_pos = i + 1

                                    if insert_pos == 0:
                                        # Find position after docstring
                                        for i, line in enumerate(lines):
                                            if line.strip() and not line.strip().startswith('#'):
                                                if not (line.strip().startswith('"""') or line.strip().startswith("'''")):
                                                    insert_pos = i
                                                    break

                                    lines.insert(insert_pos, import_stmt)

                                    with open(filepath, 'w', encoding='utf-8') as f:
                                        f.write('\n'.join(lines))
                                    print(f"   ✅ Fixed: {filepath}")
                                else:
                                    print(f"   ℹ️  Import already exists: {import_stmt}")
                    except Exception as fix_error:
                        print(f"   ⚠️  Could not fix: {fix_error}")

    except SyntaxError as e:
        print(f"❌ SyntaxError: {e}")
        print(f"   In: {e.filename}:{e.lineno}")
        print(f"   {e.text}")
        break

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        last_error = e
        traceback.print_exc()
        break

print(f"\n{'='*60}")
if attempt >= max_attempts:
    print(f"❌ Failed after {max_attempts} attempts")
    if last_error:
        print(f"Last error: {last_error}")
else:
    print(f"✅ Success after {attempt} attempt(s)")
