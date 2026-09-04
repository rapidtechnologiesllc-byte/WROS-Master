#!/usr/bin/env python3
"""Clean up duplicate logger.error calls left by auto-fixer."""
import os
import re

def cleanup_file(file_path):
    """Remove duplicate generic logger.error calls."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return 0

    original = content

    # Remove generic "logger.error(f"Error: {str(e)}", exc_info=True)" that is followed by specific error
    # Pattern: generic error on one line followed by indented specific error
    pattern = r'(\s+)logger\.error\(f"Error: \{str\(e\)\}", exc_info=True\)\n(\s+)logger\.error\(f"Failed to'
    replacement = r'\2logger.error(f"Failed to'

    content = re.sub(pattern, replacement, content)

    # Also fix indentation issues (lines starting with extra space before logger)
    pattern2 = r'\n(\s+)logger\.error\(f"Error:'
    replacement2 = r'\nlogger.error(f"Error:'

    if content != original:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        except:
            return 0

    return 0

def main():
    """Clean up all Python files."""
    backend_dir = r'C:\dev\WROS-Master\backend'
    fixed_count = 0

    for root, dirs, files in os.walk(backend_dir):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if cleanup_file(file_path):
                    fixed_count += 1
                    rel_path = os.path.relpath(file_path, backend_dir)
                    print(f"[OK] {rel_path}: cleaned up duplicates")

    print(f"\n[SUMMARY] {fixed_count} files cleaned")

if __name__ == '__main__':
    main()
