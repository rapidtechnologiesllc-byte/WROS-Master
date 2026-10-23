#!/usr/bin/env python3
"""Fix all department_id type mismatches: Integer -> String(36)"""

import re
from pathlib import Path

models_dir = Path('app/models')
fixed = 0

for model_file in sorted(models_dir.glob('*.py')):
    if model_file.name.startswith('__'):
        continue

    with open(model_file, 'r') as f:
        content = f.read()

    original = content

    # Fix: department_id = Column(Integer, ForeignKey('departments.id')...)
    # Should be: department_id = Column(String(36), ForeignKey('departments.id')...)
    pattern = r'(\s+department_id\s*=\s*Column\(\s*)Integer(\s*,\s*ForeignKey\(\s*["\']departments\.id)'
    new_content = re.sub(pattern, r'\1String(36)\2', content)

    if new_content != content:
        fixed += 1
        with open(model_file, 'w') as f:
            f.write(new_content)
        print(f'✓ Fixed: {model_file.name}')

print(f'\n✅ Total fixed: {fixed} files')
