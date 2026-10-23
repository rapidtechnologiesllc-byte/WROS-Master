#!/usr/bin/env python3
"""
Automatically fix CRITICAL severity issues: Missing permission checks
Adds proper role template permission enforcement to endpoints
"""
import os
import re

class CriticalPermissionFixer:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.fixes_applied = 0
        self.files_modified = []

    def add_permission_check(self, content, file_path):
        """Add missing permission checks to endpoints."""
        original = content
        lines = content.split('\n')
        new_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)

            # Pattern: @router endpoint decorator without permission check
            if re.search(r'@router\.(get|post|put|delete|patch)', line):
                # Look ahead to see if this is a public endpoint
                is_public = False
                decorator_section = []
                j = i
                while j < min(i + 15, len(lines)):
                    if 'public' in lines[j].lower() or 'skip_auth' in lines[j].lower():
                        is_public = True
                        break
                    if 'def ' in lines[j]:
                        decorator_section = lines[i:j]
                        break
                    j += 1

                if not is_public and decorator_section:
                    # Check if permission check already exists
                    has_permission = False
                    for deco_line in decorator_section:
                        if any(x in deco_line for x in [
                            'require_resource_permission',
                            'require_admin_role',
                            'require_permission',
                            'Depends(get_current_user)',
                            'Depends(get_current_hr_or_admin)',
                            'dependencies='
                        ]):
                            has_permission = True
                            break

                    # If no permission check found, add one
                    if not has_permission and 'def ' in lines[min(i+1, len(lines)-1)]:
                        # Determine endpoint method
                        method_match = re.search(r'@router\.(\w+)', line)
                        if method_match:
                            method = method_match.group(1).upper()
                            route_match = re.search(r'["\']([^"\']+)["\']', line)
                            route = route_match.group(1) if route_match else 'unknown'

                            # Add permission check decorator
                            indent = len(line) - len(line.lstrip())

                            # Determine appropriate resource from endpoint path
                            resource = determine_resource(route, method)
                            action = determine_action(method)

                            # Add the permission decorator
                            new_lines.append(' ' * indent + f'    dependencies=[Depends(require_resource_permission("{resource}", "{action}"))]')

            i += 1

        return '\n'.join(new_lines)

    def add_endpoint_guards(self, content):
        """Add guard clauses for endpoints requiring current_user."""
        lines = content.split('\n')
        new_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)

            # Pattern: async def endpoint(...): without permission check
            if 'async def ' in line or (('def ' in line) and '@router' in '\n'.join(lines[max(0, i-5):i])):
                # Check if function has current_user parameter
                has_current_user = 'current_user' in line
                has_permission_check = 'require_resource_permission' in '\n'.join(lines[max(0, i-5):i])

                if has_current_user and not has_permission_check:
                    # Add guard clause after function definition
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        indent = len(next_line) - len(next_line.lstrip())

                        # Check if docstring follows
                        if '"""' in next_line or "'''" in next_line:
                            # Skip docstring
                            docstring_end = i + 2
                            for j in range(i + 2, len(lines)):
                                if '"""' in lines[j] or "'''" in lines[j]:
                                    docstring_end = j
                                    break
                            i = docstring_end + 1
                            new_lines.extend(lines[i+1:docstring_end+1])

                        # Add guard after docstring
                        new_lines.append(' ' * (indent + 4) + 'if not current_user:')
                        new_lines.append(' ' * (indent + 8) + 'raise HTTPException(status_code=401, detail="Authentication required")')

            i += 1

        return '\n'.join(new_lines)

    def fix_file(self, file_path):
        """Apply permission check fixes to a file."""
        # Skip non-endpoint files
        if 'endpoints' not in file_path:
            return 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return 0

        original_content = content
        fixes = 0

        # Check if file has endpoints
        if '@router.' not in content:
            return 0

        # Apply permission check additions
        new_content = self.add_permission_check(content, file_path)
        if new_content != original_content:
            fixes += 1

        # Apply endpoint guard clauses
        new_content = self.add_endpoint_guards(new_content)
        if new_content != original_content:
            fixes += 1

        if fixes > 0:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                self.fixes_applied += fixes
                self.files_modified.append(file_path)
                return fixes
            except:
                return 0

        return 0

    def run(self):
        """Scan and fix all endpoint files."""
        fixed_count = 0

        for root, dirs, files in os.walk(self.backend_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

            for file in files:
                if file.endswith('.py') and 'endpoints' in root:
                    file_path = os.path.join(root, file)
                    fixes = self.fix_file(file_path)
                    if fixes > 0:
                        fixed_count += 1
                        rel_path = os.path.relpath(file_path, self.backend_dir)
                        print(f"[CRITICAL-FIXED] {rel_path}: {fixes} permission check(s) added")

        print(f"\n[SUMMARY] {fixed_count} endpoint files secured with permission checks")
        return fixed_count > 0

def determine_resource(route, method):
    """Determine resource type from endpoint route."""
    # Extract resource from route path
    route_parts = route.strip('/').split('/')
    if route_parts:
        resource = route_parts[0]
        # Singularize common resources
        resource_singular = {
            'candidates': 'candidate',
            'jobs': 'job',
            'interviews': 'interview',
            'offers': 'offer',
            'employees': 'employee',
            'users': 'user',
            'invoices': 'invoice',
            'tasks': 'task',
            'projects': 'project',
            'timesheets': 'timesheet',
        }
        return resource_singular.get(resource, resource.rstrip('s'))
    return 'resource'

def determine_action(method):
    """Determine action type from HTTP method."""
    action_map = {
        'GET': 'view',
        'POST': 'create',
        'PUT': 'update',
        'PATCH': 'update',
        'DELETE': 'delete',
    }
    return action_map.get(method.upper(), 'access')

if __name__ == '__main__':
    backend = r'C:\dev\WROS-Master\backend'
    fixer = CriticalPermissionFixer(backend)
    if fixer.run():
        print(f"[OK] CRITICAL permission checks complete! {len(fixer.files_modified)} endpoint files secured.")
    else:
        print("[OK] No missing permission checks found or all already protected.")
