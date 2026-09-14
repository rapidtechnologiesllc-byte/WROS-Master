#!/usr/bin/env python3
"""
Fix corrupted FastAPI route decorators from commit 343b71f7.

Pattern: Orphaned decorator parameters without @router.METHOD( prefix.

BROKEN:
    dependencies=[Depends(...)],
    "/path",
    dependencies=[Depends(...)],
    summary="...",
)
async def endpoint():

FIXED:
@router.get(  # or .post, .put, .delete, .patch
    "/path",
    dependencies=[Depends(...)],
    summary="...",
)
async def endpoint():
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

ENDPOINT_FILES = [
    "app/api/v1/endpoints/checklists.py",
    "app/api/v1/endpoints/core_pull.py",
    "app/api/v1/endpoints/demand_confirmation.py",
    "app/api/v1/endpoints/documents.py",
    "app/api/v1/endpoints/email.py",
    "app/api/v1/endpoints/employee_milestones.py",
    "app/api/v1/endpoints/executive_signal.py",
    "app/api/v1/endpoints/interviews.py",
    "app/api/v1/endpoints/offer_letters.py",
    "app/api/v1/endpoints/revenue.py",
    "app/api/v1/endpoints/revenue_recognition.py",
    "app/api/v1/endpoints/resource_forecast.py",
    "app/api/v1/endpoints/submissions.py",
    "app/api/v1/endpoints/whatsapp_webhook.py",
    "app/api/v1/endpoints/business_units.py",
    "app/api/v1/endpoints/ai_recruiter_assignment.py",
    "app/api/v1/endpoints/autonomous_job_management.py",
    "app/api/v1/endpoints/error_log.py",
    "app/api/v1/endpoints/flash.py",
    "app/api/v1/endpoints/htd_intake_pause.py",
    "app/api/v1/endpoints/invoices_s316.py",
    "app/api/v1/endpoints/org_structure.py",
    "app/api/v1/endpoints/portal_messages.py",
    "app/api/v1/endpoints/preboarding.py",
    "app/api/v1/endpoints/resource_management.py",
]

def detect_method(func_def: str, next_lines: str) -> str:
    """Detect HTTP method from async def or nearby context."""
    if "async def" in func_def:
        return "post"  # Default async to POST (safe for handlers)

    if "def " in func_def:
        # Check next lines for hints about the method
        if "current_user" in next_lines or "get_current" in next_lines:
            return "get"  # User profile reads are typically GET
        return "get"  # Default to GET for simple def

    return "get"

def infer_method_from_path(path: str, func_name: str) -> str:
    """Infer HTTP method from path and function name."""
    # POST patterns
    if any(x in path for x in ["/create", "/assign", "/decide", "/record", "/mark", "/remove", "/send", "/submit"]):
        return "post"
    if any(x in func_name for x in ["create", "assign", "decide", "record", "mark", "remove", "send", "submit"]):
        return "post"

    # PUT/PATCH patterns
    if any(x in path for x in ["/update", "/{", "change"]):
        if "update" in func_name:
            return "put"

    # DELETE patterns
    if "delete" in path or "remove" in path:
        return "delete"

    # Default to GET
    return "get"

def fix_corrupted_decorators(filepath: str) -> Tuple[int, List[str]]:
    """Fix corrupted decorators in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    fixed_lines = []
    i = 0
    fixes_made = []

    while i < len(lines):
        line = lines[i]

        # Look for orphaned dependencies= at start of line (4 space indent)
        if line.startswith('    dependencies=[Depends(') and (i == 0 or not lines[i-1].strip().startswith('@router')):
            # Found corrupted decorator block
            # Collect all lines until we find the async/def
            decorator_lines = [line]
            i += 1

            path = None
            while i < len(lines) and not (lines[i].strip().startswith('async def ') or lines[i].strip().startswith('def ')):
                decorator_lines.append(lines[i])
                if '    "/' in lines[i] or '    "' in lines[i]:
                    # Extract path
                    match = re.search(r'"([^"]*)"', lines[i])
                    if match:
                        path = match.group(1)
                i += 1

            if i < len(lines) and path:
                func_line = lines[i]
                func_name = re.search(r'def\s+(\w+)', func_line)
                if func_name:
                    func_name = func_name.group(1)

                    # Infer HTTP method
                    method = infer_method_from_path(path, func_name)

                    # Build fixed decorator
                    fixed_decorator = [f"@router.{method}(", f'    "{path}",']

                    # Add other parameters (skip first dependencies= and path)
                    for j, dline in enumerate(decorator_lines):
                        if j == 0:  # Skip first dependencies=
                            # Extract the dependencies to re-add
                            if 'dependencies=[Depends(' in dline:
                                # Extract and clean
                                pass
                        elif '    "/' in dline or '    "' in dline:
                            # Skip path (already added)
                            pass
                        elif 'dependencies=' in dline:
                            # Keep this dependencies line
                            fixed_decorator.append(dline)
                        elif dline.strip():
                            # Keep other params
                            fixed_decorator.append(dline)

                    # Add closing paren
                    fixed_decorator.append(')')

                    # Replace in output
                    fixed_lines.extend(fixed_decorator)
                    fixed_lines.append(func_line)

                    fixes_made.append(f"{Path(filepath).name}: {func_name} ({method.upper()} {path})")
            else:
                # Failed to parse, keep original
                fixed_lines.extend(decorator_lines)
                if i < len(lines):
                    fixed_lines.append(lines[i])
                i += 1
        else:
            fixed_lines.append(line)
            i += 1

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))

    return len(fixes_made), fixes_made

def main():
    """Main fix function."""
    total_fixes = 0
    all_fixes = []

    for endpoint_file in ENDPOINT_FILES:
        filepath = Path(endpoint_file)
        if not filepath.exists():
            print(f"⚠️  Skip {endpoint_file} (not found)")
            continue

        try:
            num_fixes, fixes = fix_corrupted_decorators(str(filepath))
            if num_fixes > 0:
                total_fixes += num_fixes
                all_fixes.extend(fixes)
                print(f"✅ {endpoint_file}: {num_fixes} fixes")
            else:
                print(f"ℹ️  {endpoint_file}: No corruptions found")
        except Exception as e:
            print(f"❌ {endpoint_file}: {e}")

    print(f"\n{'='*60}")
    print(f"TOTAL FIXES: {total_fixes}")
    for fix in all_fixes:
        print(f"  - {fix}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
