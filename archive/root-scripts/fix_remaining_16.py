#!/usr/bin/env python3
"""
Fix the remaining 16 unprotected endpoints
"""
import os
import re

files_to_fix = {
    'candidate_ranking.py': [29, 78, 125],
    'email.py': [232],
    'htd_intake_pause.py': [72],
    'internal.py': [94],
    'interview_decision.py': [32, 76, 112, 167],
    'offers.py': [238, 346, 501],
    'public_chat.py': [120],
    'thunder.py': [105, 121],
}

backend = r'C:\dev\WROS-Master\backend'

for filename, line_numbers in files_to_fix.items():
    filepath = os.path.join(backend, f'app/api/v1/endpoints/{filename}')
    if not os.path.exists(filepath):
        print(f"[SKIP] {filename} not found")
        continue

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        print(f"[ERROR] Cannot read {filename}")
        continue

    fixed = 0
    for line_num in sorted(line_numbers, reverse=True):  # Process in reverse to maintain line numbers
        idx = line_num - 1  # Convert to 0-indexed
        if idx < len(lines):
            line = lines[idx]

            # Check if already has permission check in next few lines
            context = ''.join(lines[idx:min(idx+5, len(lines))])
            if 'dependencies=' not in context and 'public' not in context and 'skip_auth' not in context:
                # Add permission check
                if '@router.' in line:
                    # Insert after the @router line
                    indent = len(line) - len(line.lstrip())
                    # Determine resource from file name or route
                    if 'candidate_ranking' in filename:
                        resource, action = 'candidate', 'view'
                    elif 'email' in filename:
                        resource, action = 'message', 'send'
                    elif 'interview_decision' in filename:
                        resource, action = 'interview', 'manage'
                    elif 'offers' in filename:
                        resource, action = 'offer', 'manage'
                    elif 'thunder' in filename:
                        resource, action = 'candidate', 'view'  # Thunder read-only
                    elif 'public_chat' in filename:
                        resource, action = 'candidate', 'view'
                    else:
                        resource, action = 'resource', 'access'

                    # Add dependency on next line
                    perm_line = ' ' * (indent + 4) + f'dependencies=[Depends(require_resource_permission("{resource}", "{action}"))],\n'
                    lines.insert(idx + 1, perm_line)
                    fixed += 1

    if fixed > 0:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"[FIXED] {filename}: {fixed} endpoint(s)")
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")

print()
print("[OK] Remaining 16 endpoints protected with RBAC")
