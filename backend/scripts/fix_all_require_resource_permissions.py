#!/usr/bin/env python3
"""
Fix all endpoint files that use require_resource_permission but don't import it,
and fix malformed decorator arguments.
"""

import os
import re
import sys
from pathlib import Path

ENDPOINTS_DIR = Path(__file__).parent.parent / "app" / "api" / "v1" / "endpoints"

def fix_file(filepath):
    """Fix a single endpoint file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Check if file uses require_resource_permission
    if 'require_resource_permission' not in content:
        return False, "No usage found"

    # Fix 1: Add missing import
    if 'from app.core.dependencies import' in content and 'require_resource_permission' not in content:
        # Find the import line and add require_resource_permission
        pattern = r'(from app\.core\.dependencies import [^\n]+)'

        def add_to_import(match):
            imports_line = match.group(1)
            # Check if it's a single line import or multi-line
            if imports_line.endswith(','):
                return imports_line + '\n    require_resource_permission,'
            elif '(' in imports_line:
                # Multi-line import
                return imports_line.rstrip(')') + ',\n    require_resource_permission,\n)'
            else:
                return imports_line + ', require_resource_permission'

        content = re.sub(pattern, add_to_import, content, count=1)

    # Fix 2: Fix malformed require_resource_permission calls
    # Pattern: require_resource_permission(", response_model=..., summary=", "action")
    malformed_pattern = r'require_resource_permission\("[^"]*,\s*response_model[^"]*",\s*"([^"]+)"\)'

    def fix_malformed(match):
        action = match.group(1)
        resource = filepath.stem  # Use filename as resource
        return f'require_resource_permission("{resource}", "{action}")'

    content = re.sub(malformed_pattern, fix_malformed, content)

    # Fix 3: Fix resource names like "{allocation_id}" to just the resource
    pattern3 = r'require_resource_permission\("\{[^\}]+\}",\s*"([^"]+)"\)'

    def fix_resource_name(match):
        action = match.group(1)
        resource = filepath.stem
        return f'require_resource_permission("{resource}", "{action}")'

    content = re.sub(pattern3, fix_resource_name, content)

    # Check if file changed
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, "Fixed"

    return False, "No changes needed"

def main():
    """Find and fix all endpoint files."""
    endpoint_files = sorted(ENDPOINTS_DIR.glob('**/*.py'))

    print(f"Found {len(endpoint_files)} endpoint files")
    print()

    fixed_count = 0
    for filepath in endpoint_files:
        if '__pycache__' in str(filepath) or filepath.name == '__init__.py':
            continue

        changed, reason = fix_file(filepath)
        if changed:
            print(f"✅ {filepath.relative_to(ENDPOINTS_DIR.parent.parent)}: {reason}")
            fixed_count += 1
        elif 'No usage found' not in reason:
            print(f"   {filepath.relative_to(ENDPOINTS_DIR.parent.parent)}: {reason}")

    print()
    print(f"Fixed {fixed_count} files")

if __name__ == '__main__':
    main()
