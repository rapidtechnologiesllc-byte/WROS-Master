#!/usr/bin/env python3
"""
Remove conflicting index=True declarations when explicit Index() exists in __table_args__
import logging
"""

import re
from pathlib import Path

models_dir = Path("app/models")

# Columns that commonly have explicit Index() definitions should not have index=True
# Common pattern: tenant_id, active, status, created_at, updated_at
common_indexed_columns = [
    "tenant_id", "active", "status", "created_at", "updated_at",
    "role_id", "permission_id", "job_id", "candidate_id", "user_id"
]

fixed_count = 0

for model_file in sorted(models_dir.glob("*.py")):
    if model_file.name.startswith("__"):
        continue

    with open(model_file, 'r') as f:
        content = f.read()

    original_content = content

    # Find all __table_args__ blocks and extract column names used in Index()
    table_args_pattern = r'__table_args__\s*=\s*\((.*?)\)'
    table_args_match = re.search(table_args_pattern, content, re.DOTALL)

    if not table_args_match:
        continue

    table_args_content = table_args_match.group(1)

    # Extract all columns mentioned in Index() definitions
    index_pattern = r'Index\([^)]+,\s*([^)]+)\)'
    indexed_columns_in_args = set()

    for match in re.finditer(index_pattern, table_args_content):
        columns_str = match.group(1)
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(',')]
        indexed_columns_in_args.update(columns)

    if not indexed_columns_in_args:
        continue

    # Remove index=True from these columns
    for col in indexed_columns_in_args:
        # Pattern: column = Column(..., index=True, ...)
        patterns = [
            (rf'({col}\s*=\s*Column\([^)]*?),\s*index\s*=\s*True([^)]*?\))', r'\1\2'),
            (rf'({col}\s*=\s*Column\([^)]*?index\s*=\s*True),\s*([^)]*?\))', r'\1\2'),
        ]

        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                fixed_count += 1
                content = new_content
                print(f"  ✓ Removed index=True from {col}")

    if content != original_content:
        with open(model_file, 'w') as f:
            f.write(content)
        print(f"✓ Fixed {model_file.name}")

print(f"\n✅ Fixed {fixed_count} conflicting index definitions")
