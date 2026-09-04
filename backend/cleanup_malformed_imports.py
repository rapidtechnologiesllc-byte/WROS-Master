#!/usr/bin/env python3
"""Clean up malformed imports created by bulk fixer"""

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).parent

def clean_imports(filepath):
    """Remove duplicate and malformed imports"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Remove duplicate "from app.core.dependencies import" lines
    lines = content.split('\n')
    seen_imports = set()
    cleaned_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip lines that are part of malformed imports
        if skip_next:
            if stripped and not stripped.startswith('from') and not stripped.startswith('import') and not stripped.startswith(')'):
                skip_next = False
            else:
                continue

        if stripped.startswith('from ') and ' import ' in stripped:
            # Extract the full import statement
            full_import = stripped

            # Check if it has multiple "from...import" on one line
            if full_import.count(' import ') > 1:
                # Split and clean
                parts = full_import.split(' import ')
                first_part = parts[0]  # "from app.core.dependencies"
                last_part = parts[-1]   # last part after last "import"

                # Reconstruct: "from app.core.dependencies import last_part"
                if '(' in last_part:
                    # Multi-line import, don't clean
                    cleaned_lines.append(line)
                else:
                    cleaned_import = f"{first_part} import {last_part}"
                    if cleaned_import not in seen_imports:
                        cleaned_lines.append(cleaned_import)
                        seen_imports.add(cleaned_import)
                continue

            if full_import not in seen_imports:
                cleaned_lines.append(line)
                seen_imports.add(full_import)
            continue

        # Handle regular imports and other lines
        cleaned_lines.append(line)

    new_content = '\n'.join(cleaned_lines)

    # Remove excess blank lines
    new_content = re.sub(r'\n\n\n+', '\n\n', new_content)

    if new_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

# Scan and clean all Python files
fixed_count = 0
for pyfile in BACKEND_DIR.rglob("*.py"):
    if '__pycache__' in str(pyfile):
        continue

    if clean_imports(pyfile):
        rel_path = pyfile.relative_to(BACKEND_DIR.parent.parent)
        print(f"✅ Cleaned: {rel_path}")
        fixed_count += 1

print(f"\n✅ Total files cleaned: {fixed_count}")
