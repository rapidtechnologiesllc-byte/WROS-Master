#!/usr/bin/env python3
"""Find duplicate constraint names across all models"""

import re
from pathlib import Path
from collections import defaultdict

models_dir = Path('app/models')
constraints = defaultdict(list)

for model_file in sorted(models_dir.glob('*.py')):
    if model_file.name.startswith('__'):
        continue

    with open(model_file, 'r') as f:
        content = f.read()

    # Find UniqueConstraint definitions
    unique_pattern = r'UniqueConstraint\([^)]+,\s*name=["\']([^"\']+)["\']'
    for match in re.finditer(unique_pattern, content):
        constraint_name = match.group(1)
        constraints[constraint_name].append(model_file.name)

# Find duplicates
duplicates = {k: v for k, v in constraints.items() if len(v) > 1}

if duplicates:
    print("❌ DUPLICATE CONSTRAINT NAMES FOUND:\n")
    for constraint_name, files in sorted(duplicates.items()):
        print(f"  '{constraint_name}' in: {', '.join(files)}")
else:
    print("✅ No duplicate constraint names found")
