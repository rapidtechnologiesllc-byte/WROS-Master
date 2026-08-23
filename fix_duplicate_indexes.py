#!/usr/bin/env python3
"""
Fix duplicate index definitions across all models.

Problem: Models define indexes both via index=True on Column AND via explicit Index()
Result: CREATE INDEX fails with "relation already exists"

Solution: Remove index=True when Index() is defined in __table_args__
"""

import os
import re
from pathlib import Path

def find_duplicate_indexes(model_path):
    """Find models with duplicate index definitions"""
    with open(model_path, 'r') as f:
        content = f.read()

    # Find all Index() definitions in __table_args__ (handle multiple columns)
    index_pattern = r'Index\("([^"]+)",\s*([^)]+)\)'
    indexes_in_args = []

    for match in re.finditer(index_pattern, content):
        index_name = match.group(1)
        columns_str = match.group(2)
        # Split by comma and clean up
        columns = [col.strip().strip('"') for col in columns_str.split(',')]
        indexes_in_args.append((index_name, columns))

    if not indexes_in_args:
        return None

    duplicates = []
    for index_name, columns in indexes_in_args:
        for column_name in columns:
            # Check if this column also has index=True
            col_pattern = rf'{column_name}\s*=\s*Column\([^)]*index\s*=\s*True[^)]*\)'
            if re.search(col_pattern, content):
                duplicates.append({
                    'column': column_name,
                    'index_name': index_name,
                    'model_file': model_path
                })

    return duplicates if duplicates else None


def fix_duplicate_indexes_in_file(file_path):
    """Remove index=True from columns that have explicit Index() in __table_args__"""
    with open(file_path, 'r') as f:
        content = f.read()

    original = content

    # Find all Index() definitions to get column names
    index_pattern = r'Index\("([^"]+)",\s*"?([^")\s,]+)"?\)'
    indexed_columns = set(match[1] for match in re.finditer(index_pattern, content))

    if not indexed_columns:
        return 0  # No indexes defined

    # For each indexed column, remove index=True from the Column definition
    fixed_count = 0
    for col in indexed_columns:
        # Pattern: column_name = Column(..., index=True, ...)
        pattern = rf'({col}\s*=\s*Column\([^)]*?),?\s*index=True(,?\s*[^)]*?\))'
        replacement = r'\1\2'

        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixed_count += 1
            content = new_content

    if fixed_count > 0:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✓ Fixed {fixed_count} columns in {os.path.basename(file_path)}")
        return fixed_count

    return 0


def main():
    models_dir = Path("C:\\Users\\AvinashMukund\\Documents\\Claude\\OnboardingModule-Backend\\app\\models")

    total_fixed = 0
    files_with_issues = []

    for model_file in sorted(models_dir.glob("*.py")):
        if model_file.name.startswith("__"):
            continue

        duplicates = find_duplicate_indexes(model_file)
        if duplicates:
            files_with_issues.append(model_file)
            print(f"\n📝 {model_file.name}:")
            for dup in duplicates:
                print(f"   Column '{dup['column']}' has both index=True AND Index('{dup['index_name']}')")

    if files_with_issues:
        print(f"\n{'='*70}")
        print(f"Found {len(files_with_issues)} files with duplicate indexes")
        print(f"{'='*70}\n")

        for model_file in files_with_issues:
            fixed = fix_duplicate_indexes_in_file(model_file)
            total_fixed += fixed

    print(f"\n{'='*70}")
    if total_fixed > 0:
        print(f"✅ Fixed {total_fixed} duplicate index definitions")
        print(f"   Removed index=True from columns that have explicit Index()")
    else:
        print(f"✅ No duplicate indexes found or already fixed")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
