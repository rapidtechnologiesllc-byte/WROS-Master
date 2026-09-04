#!/usr/bin/env python3
"""
Active Routes Only Scanner
Identifies orphaned/dead code files that exist but aren't registered in the app
"""
import os
import sys
import logging
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_registered_endpoints():
    """Find all endpoint files that are actually registered in app/api/v1/routes.py"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    routes_file = os.path.join(backend_dir, 'app/api/v1/routes.py')

    with open(routes_file, 'r') as f:
        content = f.read()

    registered = set()

    # Find all import statements: from app.api.v1.endpoints.xxx import
    for line in content.split('\n'):
        if 'from app.api.v1.endpoints' in line:
            # Extract filename
            parts = line.split('.')
            if len(parts) >= 5:
                module_name = parts[4].split()[0]
                endpoint_file = f"{module_name}.py"
                registered.add(endpoint_file)

    return registered

def find_all_endpoint_files():
    """Find all .py files in endpoints directory"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    endpoints_dir = os.path.join(backend_dir, 'app/api/v1/endpoints')

    all_files = set()
    for root, dirs, files in os.walk(endpoints_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.py') and not file.startswith('test_') and file != '__init__.py':
                all_files.add(file)

    return all_files

def main():
    registered = find_registered_endpoints()
    all_files = find_all_endpoint_files()

    orphaned = all_files - registered

    print("\n" + "="*60)
    print("ENDPOINT REGISTRATION AUDIT")
    print("="*60 + "\n")

    print(f"Total endpoint files: {len(all_files)}")
    print(f"Registered in app: {len(registered)}")
    print(f"Orphaned (not registered): {len(orphaned)}\n")

    if orphaned:
        print("🚨 ORPHANED ENDPOINT FILES (Not in routes.py):")
        print("="*60)
        for file in sorted(orphaned):
            print(f"  ❌ {file}")

        print("\n⚠️  These files exist in the codebase but are NOT registered.")
        print("    They won't run even if someone tries to access them.")
        print("    Consider:")
        print("    1. Delete if truly dead code")
        print("    2. Register in app/api/v1/routes.py if they should be active")
        print("    3. Move to 'backlog' or 'archived' folder")
    else:
        print("✅ No orphaned endpoint files detected!")

    print("\n" + "="*60)
    print("REGISTERED ENDPOINTS:")
    print("="*60)
    for file in sorted(registered):
        print(f"  ✅ {file}")

if __name__ == '__main__':
    main()
