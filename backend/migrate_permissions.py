#!/usr/bin/env python3
"""
Comprehensive RBAC permission decorator migration script.
Converts all OLD @require_permission decorators to NEW dependencies-based approach.
"""
import os
import re

# Mapping of old permissions to new resource-based permissions
PERMISSION_MAPPINGS = {
    # Jobs/Recruitment
    ("recruitment", "view"): ("jobs", "view"),
    ("recruitment", "create"): ("jobs", "create"),
    ("recruitment", "edit"): ("jobs", "edit"),
    ("recruitment", "delete"): ("jobs", "delete"),

    # Projects
    ("project", "view"): ("projects", "view"),
    ("project", "create"): ("projects", "create"),
    ("project", "edit"): ("projects", "edit"),
    ("project", "delete"): ("projects", "delete"),

    # Timesheets (from employee.*)
    ("employee", "view"): ("timesheets", "view"),
    ("employee", "create"): ("timesheets", "create"),
    ("employee", "edit"): ("timesheets", "edit"),
    ("employee", "delete"): ("timesheets", "delete"),

    # Users/Administration
    ("administration", "view"): ("users", "view"),
    ("administration", "create"): ("users", "create"),
    ("administration", "edit"): ("users", "edit"),
    ("administration", "delete"): ("users", "delete"),
}

def convert_decorator(match):
    """Convert OLD decorator to NEW dependencies format."""
    full_match = match.group(0)

    # Handle @require_permission("resource.action") style
    perm_match = re.search(r'@require_permission\("([^"]+)"\)', full_match)
    if perm_match:
        perm = perm_match.group(1)
        resource, action = perm.split(".")
        if (resource, action) in PERMISSION_MAPPINGS:
            new_resource, new_action = PERMISSION_MAPPINGS[(resource, action)]
            return f'dependencies=[Depends(require_resource_permission("{new_resource}", "{new_action}"))]'

    # Handle @require_action_permission("resource", "action") style
    action_match = re.search(r'@require_action_permission\("([^"]+)",\s*"([^"]+)"\)', full_match)
    if action_match:
        resource = action_match.group(1)
        action = action_match.group(2)
        if (resource, action) in PERMISSION_MAPPINGS:
            new_resource, new_action = PERMISSION_MAPPINGS[(resource, action)]
            return f'dependencies=[Depends(require_resource_permission("{new_resource}", "{new_action}"))]'

    return full_match

def migrate_file(filepath):
    """Migrate all decorators in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # Find all decorator patterns and convert them
    # Pattern 1: @require_permission("...")
    pattern1 = r'@require_permission\("[^"]+"\)'
    # Pattern 2: @require_action_permission("...", "...")
    pattern2 = r'@require_action_permission\("[^"]+",\s*"[^"]+"\)'

    # Find all matches
    matches1 = list(re.finditer(pattern1, content))
    matches2 = list(re.finditer(pattern2, content))

    if not matches1 and not matches2:
        return False  # No changes needed

    # Replace patterns
    for match in matches1 + matches2:
        old_decorator = match.group(0)
        new_decorator = convert_decorator(match)

        # Convert to dependencies format on router decorator line
        # Find the router decorator before this permission decorator
        lines = content[:match.start()].split('\n')
        for i in range(len(lines) - 1, -1, -1):
            if '@router.' in lines[i]:
                # Found the router decorator
                # Add dependencies to it
                router_line = lines[i]
                if 'dependencies=' not in router_line:
                    # Add dependencies
                    if router_line.endswith(')'):
                        router_line = router_line[:-1] + f', {new_decorator})'
                    else:
                        router_line += f', {new_decorator}'
                    lines[i] = router_line

                # Reconstruct content
                content = '\n'.join(lines) + '\n' + '\n'.join(content.split('\n')[len(lines):])
                # Remove the old decorator line
                content = content.replace('\n' + old_decorator + '\n', '\n')
                break

    # Remove any OLD imports
    content = re.sub(r'from app\.core\.permission_enforcement import require_permission\n', '', content)
    content = re.sub(r'from app\.core\.permission_enforcement import require_action_permission\n', '', content)
    content = re.sub(r'import require_permission\n', '', content)
    content = re.sub(r'import require_action_permission\n', '', content)

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

# Find all endpoint files
endpoint_dir = "backend/app/api/v1/endpoints"
for root, dirs, files in os.walk(endpoint_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            if migrate_file(filepath):
                print(f"✓ Migrated: {filepath}")
            else:
                print(f"  No changes: {filepath}")

print("\nMigration complete!")
