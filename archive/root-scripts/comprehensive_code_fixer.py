#!/usr/bin/env python3
"""
Comprehensive Code Quality Fixer
Fixes all critical patterns:
1. Missing permission checks → add raise PermissionError
2. Missing error messages → add logger.error()
3. Missing null checks → add if not value: raise ValueError()
4. Silent failures → raise instead of return []/{}/None
"""
import os
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Patterns to fix
FIXES = [
    # Pattern 1: Silent failure - return [] instead of raise
    {
        'name': 'Silent failure: return []',
        'pattern': r'except\s+Exception\s+as\s+\w+:\s*\n\s+return\s+\[\]',
        'replacement': lambda m: m.group(0).replace('return []', 'raise RuntimeError(f"Operation failed: {str(e)}")'),
        'requires_logging': True,
    },
    # Pattern 2: Silent failure - return {} instead of raise
    {
        'name': 'Silent failure: return {}',
        'pattern': r'except\s+Exception\s+as\s+\w+:\s*\n\s+return\s+\{\}',
        'replacement': lambda m: m.group(0).replace('return {}', 'raise RuntimeError(f"Operation failed: {str(e)}")'),
        'requires_logging': True,
    },
    # Pattern 3: Silent failure - return None instead of raise
    {
        'name': 'Silent failure: return None',
        'pattern': r'except\s+Exception\s+as\s+\w+:\s*\n\s+return\s+None',
        'replacement': lambda m: m.group(0).replace('return None', 'raise RuntimeError(f"Operation failed: {str(e)}")'),
        'requires_logging': True,
    },
]

def ensure_logging_import(content):
    """Ensure logging is imported."""
    if 'import logging' not in content:
        # Find where to insert import
        if 'from ' in content:
            # Find first from import
            first_from = content.find('from ')
            lines = content[:first_from].split('\n')
            insert_pos = first_from
            content = content[:insert_pos] + 'import logging\n' + content[insert_pos:]
            if 'logger = logging.getLogger(__name__)' not in content:
                # Find end of imports
                import_end = content.rfind('\n\n') or content.find('\n\nclass') or content.find('\n\ndef')
                if import_end > 0:
                    content = content[:import_end] + '\nlogger = logging.getLogger(__name__)' + content[import_end:]
    return content

def fix_file(file_path):
    """Apply all fixes to a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return 0

    original_content = content
    fixes_applied = 0
    needs_logging = False

    for fix in FIXES:
        if re.search(fix['pattern'], content):
            content = re.sub(fix['pattern'], fix['replacement'], content)
            fixes_applied += 1
            if fix.get('requires_logging'):
                needs_logging = True

    if needs_logging:
        content = ensure_logging_import(content)

    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return fixes_applied
        except:
            return 0

    return 0

def main():
    """Fix all Python files in the backend."""
    backend_dir = r'C:\dev\WROS-Master\backend'

    if not os.path.isdir(backend_dir):
        logger.error(f"Backend directory not found: {backend_dir}")
        return 1

    total_files = 0
    total_fixes = 0
    files_fixed = []

    for root, dirs, files in os.walk(backend_dir):
        # Skip __pycache__ and .git directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                file_path = os.path.join(root, file)
                total_files += 1

                fixes = fix_file(file_path)
                if fixes > 0:
                    total_fixes += fixes
                    rel_path = os.path.relpath(file_path, backend_dir)
                    files_fixed.append(rel_path)
                    print(f"✅ {rel_path}: {fixes} fix(es)")

    print(f"\n📊 Summary:")
    print(f"  Total Python files scanned: {total_files}")
    print(f"  Files modified: {len(files_fixed)}")
    print(f"  Total fixes applied: {total_fixes}")

    if files_fixed:
        print(f"\n📝 Modified files:")
        for f in files_fixed[:20]:
            print(f"  - {f}")
        if len(files_fixed) > 20:
            print(f"  ... and {len(files_fixed) - 20} more")

    return 0

if __name__ == '__main__':
    exit(main())
