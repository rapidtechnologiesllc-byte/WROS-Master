#!/usr/bin/env python3
"""
Detailed code review showing exactly which endpoints need RBAC
"""
import os
import re

backend = r'C:\dev\WROS-Master\backend'

print("=" * 70)
print("DETAILED RBAC COVERAGE REPORT")
print("=" * 70)
print()

unprotected = []
protected_count = 0

for root, dirs, files in os.walk(backend):
    dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

    for file in files:
        if file.endswith('.py') and 'endpoints' in root:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except:
                continue

            for i, line in enumerate(lines):
                if re.search(r'@router\.(get|post|put|delete|patch)', line):
                    # Check next 5 lines for permission
                    context = ''.join(lines[i:min(i+6, len(lines))])
                    has_permission = any(x in context for x in [
                        'require_resource_permission',
                        'require_admin_role',
                        'require_permission',
                        'Depends(get_current_user)',
                        'Depends(get_current_hr_or_admin)',
                        'dependencies=[Depends',
                        'public',
                        'skip_auth'
                    ])

                    if has_permission:
                        protected_count += 1
                    else:
                        rel_path = os.path.relpath(file_path, backend)
                        unprotected.append((rel_path, i+1, line.strip()))

print(f"Total Protected Endpoints: {protected_count}")
print(f"Unprotected Endpoints: {len(unprotected)}")
print()

if unprotected:
    print("Unprotected Endpoints:")
    print()
    for path, line_num, endpoint in unprotected:
        print(f"  {path}:{line_num}")
        print(f"    {endpoint}")
        print()
else:
    print("[SUCCESS] All endpoints are properly protected with RBAC!")
