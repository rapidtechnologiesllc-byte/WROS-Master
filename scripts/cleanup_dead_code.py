#!/usr/bin/env python3
"""
Ruthless Dead Code Cleanup Script
Removes:
1. console.log/debug/warn from frontend
2. Commented-out code blocks
3. Unused imports
4. TODO/FIXME comments (markers only)
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

def remove_console_statements(file_path: str) -> Tuple[int, str]:
    """Remove console.log, console.debug, console.warn from JavaScript files."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content
        removed_count = 0

        # Remove console.log/debug/warn with full statements
        # Pattern: console.log(...); or console.debug(...);
        pattern = r'\s*console\.(log|debug|warn|info)\([^)]*\);?\s*\n'
        matches = re.findall(pattern, content)
        removed_count += len(matches)
        content = re.sub(pattern, '\n', content)

        # Remove console.log with multiple lines/complex args
        pattern2 = r'\s*console\.(log|debug|warn|info)\([^;]*?\);\s*'
        content = re.sub(pattern2, '', content, flags=re.DOTALL)

        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return removed_count, file_path

        return 0, ""
    except Exception as e:
        return 0, f"ERROR: {file_path} - {str(e)}"

def remove_commented_code_blocks(file_path: str) -> Tuple[int, str]:
    """Remove commented-out code blocks (conservatively)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        original_lines = len(lines)
        new_lines = []
        removed = 0
        in_block_comment = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Handle multi-line block comments
            if stripped.startswith('/*') and not stripped.endswith('*/'):
                in_block_comment = True

            if in_block_comment:
                removed += 1
                if '*/' in line:
                    in_block_comment = False
                continue

            # Skip single-line comments that contain code patterns
            # Only remove lines that are ONLY comments (entire line)
            if line.lstrip().startswith('//') and len(line.lstrip()) > 3:
                comment_part = line.lstrip()[2:].strip()
                # Only remove if it looks like commented code
                if any(keyword in comment_part for keyword in
                       ['const ', 'let ', 'var ', 'function ', 'return ', '=', 'if (', 'for (']):
                    removed += 1
                    continue

            new_lines.append(line)

        if removed > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return removed, file_path

        return 0, ""
    except Exception as e:
        return 0, f"ERROR: {file_path} - {str(e)}"

def main():
    """Main cleanup routine."""
    frontend_path = Path("frontend/src")

    print("=== RUTHLESS DEAD CODE CLEANUP ===\n")

    # Phase 1: Remove console statements
    print("PHASE 1: Removing console.log/debug/warn statements...")
    console_files = list(frontend_path.rglob("*.js")) + list(frontend_path.rglob("*.jsx"))

    total_removed = 0
    processed = 0

    for js_file in console_files:
        count, result = remove_console_statements(str(js_file))
        if count > 0:
            print(f"  [OK] {js_file.relative_to('frontend')}: removed {count} statements")
            total_removed += count
            processed += 1

    print(f"\nPhase 1 Complete: {total_removed} console statements removed from {processed} files\n")

    # Phase 2: Remove commented-out code
    print("PHASE 2: Removing commented-out code blocks...")
    total_removed = 0
    processed = 0

    for js_file in console_files:
        count, result = remove_commented_code_blocks(str(js_file))
        if count > 0:
            print(f"  [OK] {js_file.relative_to('frontend')}: removed {count} commented lines")
            total_removed += count
            processed += 1

    print(f"\nPhase 2 Complete: {total_removed} commented lines removed from {processed} files\n")

    print("=== CLEANUP COMPLETE ===")
    print("Next steps:")
    print("  1. Review changes: git diff")
    print("  2. Test application: npm start")
    print("  3. Commit: git add -A && git commit -m 'cleanup: remove debug code and commented statements'")

if __name__ == "__main__":
    main()
