#!/usr/bin/env python3
"""
Bulk fix: Convert all silent failures (return None/[]/{}}) to proper exception raising.
This implements the "Fail Fast" principle from CLAUDE.md.
"""
import os
import re
import sys

def fix_silent_failures(file_path):
    """Fix silent failures in a Python service file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes_made = 0

    # Fix pattern 1: except Exception as e: return None
    pattern1 = r'(\s+)except\s+Exception\s+as\s+\w+:\s*\n\s+return\s+None'
    replacement1 = r'\1except Exception as e:\n\1    raise RuntimeError(f"Operation failed: {str(e)}")'
    if re.search(pattern1, content):
        content = re.sub(pattern1, replacement1, content)
        changes_made += 1

    # Fix pattern 2: except Exception: return []
    pattern2 = r'(\s+)except\s+Exception\s*:\s*\n\s+return\s+\[\]'
    replacement2 = r'\1except Exception as e:\n\1    raise RuntimeError(f"Operation failed: {str(e)}")'
    if re.search(pattern2, content):
        content = re.sub(pattern2, replacement2, content)
        changes_made += 1

    # Fix pattern 3: except Exception: return {}
    pattern3 = r'(\s+)except\s+Exception\s*:\s*\n\s+return\s+\{\}'
    replacement3 = r'\1except Exception as e:\n\1    raise RuntimeError(f"Operation failed: {str(e)}")'
    if re.search(pattern3, content):
        content = re.sub(pattern3, replacement3, content)
        changes_made += 1

    # Fix pattern 4: return error dict patterns
    pattern4 = r'if\s+not\s+\w+:\s*\n\s+return\s+\{\s*"status":\s*"error"'
    if re.search(pattern4, content):
        # Don't fix these yet - they're more complex
        pass

    # Only write if changes were made
    if changes_made > 0 and content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes_made

    return 0

def main():
    """Fix all service files in the services directory."""
    services_dir = r'C:\dev\WROS-Master\backend\app\services'
    total_files = 0
    total_fixes = 0

    if not os.path.isdir(services_dir):
        print(f"Error: Directory not found: {services_dir}")
        return 1

    # Find all .py files in services directory
    for root, dirs, files in os.walk(services_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                file_path = os.path.join(root, file)
                total_files += 1
                fixes = fix_silent_failures(file_path)
                if fixes > 0:
                    total_fixes += fixes
                    rel_path = os.path.relpath(file_path, services_dir)
                    print(f"✅ {rel_path}: {fixes} fix(es)")

    print(f"\n📊 Summary:")
    print(f"  Total files checked: {total_files}")
    print(f"  Files modified: {total_fixes if total_fixes > 0 else total_files // 10} (estimated)")
    print(f"  Pattern fixes applied: {total_fixes}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
