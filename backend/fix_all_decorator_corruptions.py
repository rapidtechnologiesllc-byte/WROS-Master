#!/usr/bin/env python3
"""
Emergency fixer for systematic route decorator corruptions.
Finds and fixes ALL corrupted decorators in endpoint files in one pass.
"""
import os
import re
from pathlib import Path

def fix_decorator_corruptions(filepath):
    """Fix all decorator corruptions in a single file."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    original = content
    fixes_made = 0

    # Pattern 1: Remove duplicate paths in decorators
    # @router.METHOD("path", ..., "path", ...)  →  @router.METHOD("path", ...)
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for @router decorators
        if '@router.' in line:
            # Find the closing paren of this decorator
            paren_count = line.count('(') - line.count(')')
            start = i
            end = i
            decorator_lines = [line]

            while paren_count > 0 and end < len(lines) - 1:
                end += 1
                decorator_lines.append(lines[end])
                paren_count += lines[end].count('(') - lines[end].count(')')

            # Join the decorator
            decorator_text = '\n'.join(decorator_lines)
            original_decorator = decorator_text

            # Fix 1: Remove extra closing paren before function def
            decorator_text = re.sub(
                r'\)\s*\)\s*\n\s*def\s+',
                ')\ndef ',
                decorator_text
            )

            # Fix 2: Remove duplicate paths
            # Find all quoted strings in decorator
            parts = re.split(r'("[^"]*")', decorator_text)
            quotes = [p for p in parts if p.startswith('"') and p.endswith('"')]

            if len(quotes) >= 2:
                first_path = quotes[0]
                # Look for duplicate later in decorator
                remaining = decorator_text[decorator_text.find(first_path) + len(first_path):]
                if first_path in remaining:
                    # Remove the duplicate
                    decorator_text = decorator_text[:decorator_text.rfind(first_path)]
                    # Re-add closing bracket/paren
                    if not decorator_text.rstrip().endswith(')'):
                        decorator_text += '\n)'

            # Fix 3: Consolidate split dependencies
            decorator_text = re.sub(
                r'require_resource_permission\("([^"]+)",\s*\n\s*"([^"]+)"\)',
                r'require_resource_permission("\1", "\2")',
                decorator_text
            )

            # Fix 4: Change GET to POST where appropriate (detect by body/Request in function)
            if i < len(lines) - 20:
                upcoming = '\n'.join(lines[end+1:min(end+10, len(lines))])
                if ('Request' in upcoming and 'body:' in upcoming) or 'request:' in upcoming.lower():
                    decorator_text = decorator_text.replace('@router.get(', '@router.post(')

            if decorator_text != original_decorator:
                # Replace in lines
                new_decorator_lines = decorator_text.split('\n')
                lines[start:end+1] = new_decorator_lines
                fixes_made += 1
                i = start + len(new_decorator_lines)
            else:
                i = end + 1
        else:
            i += 1

    content = '\n'.join(lines)

    # Write back only if there were changes
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return fixes_made

    return 0

def main():
    endpoints_dir = "app/api/v1/endpoints"
    total_fixes = 0

    for filename in sorted(os.listdir(endpoints_dir)):
        if not filename.endswith('.py'):
            continue

        filepath = os.path.join(endpoints_dir, filename)
        fixes = fix_decorator_corruptions(filepath)
        if fixes > 0:
            print(f"[OK] {filename}: {fixes} corruptions fixed")
            total_fixes += fixes

    print(f"\n[TOTAL] {total_fixes} corruptions fixed")

    # Verify compilation
    errors = []
    for filename in os.listdir(endpoints_dir):
        if not filename.endswith('.py'):
            continue
        filepath = os.path.join(endpoints_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                compile(f.read(), filename, 'exec')
        except SyntaxError as e:
            errors.append(f"{filename}:{e.lineno}")

    if errors:
        print(f"\n[ERRORS] {len(errors)} files still have syntax errors:")
        for e in errors[:10]:
            print(f"  {e}")
    else:
        print("[SUCCESS] ALL ENDPOINT FILES COMPILE!")

if __name__ == "__main__":
    main()
