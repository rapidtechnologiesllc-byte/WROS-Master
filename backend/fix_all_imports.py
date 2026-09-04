#!/usr/bin/env python3
import re
from pathlib import Path

backend = Path(".")
fixed_count = 0

for pyfile in backend.rglob("*.py"):
    if '__pycache__' in str(pyfile):
        continue

    try:
        with open(pyfile, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        continue

    if 'require_resource_permission(' not in content:
        continue

    if 'require_resource_permission' in content and (', require_resource_permission' in content or '(require_resource_permission' in content):
        continue

    if 'from app.core.dependencies import' in content:
        new_content = re.sub(
            r'(from app\.core\.dependencies import [^\n]+?)(?:\))?(?=\n)',
            lambda m: m.group(1).rstrip(')') + ', require_resource_permission)\n' if ')' in m.group(1) else m.group(1).rstrip() + ', require_resource_permission\n',
            content,
            count=1
        )

        if new_content != content:
            with open(pyfile, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed_count += 1
            print(f"Fixed: {pyfile}")

print(f"\nTotal: {fixed_count} files")
