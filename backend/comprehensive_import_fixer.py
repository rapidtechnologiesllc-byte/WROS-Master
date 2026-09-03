#!/usr/bin/env python3

import ast
import os
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).parent
errors = defaultdict(list)

def get_missing_names(filepath):
    """Compile and identify undefined names in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Try to compile
        try:
            compile(content, str(filepath), 'exec')
            return []
        except NameError as e:
            # Extract undefined name
            msg = str(e)
            if "name '" in msg and "' is not defined" in msg:
                name = msg.split("name '")[1].split("'")[0]
                return [name]
            return []
        except SyntaxError:
            return []
    except Exception:
        return []

# Scan all Python files
for pyfile in sorted(BACKEND_DIR.rglob("*.py")):
    if '__pycache__' in str(pyfile):
        continue

    missing = get_missing_names(pyfile)
    if missing:
        rel_path = pyfile.relative_to(BACKEND_DIR)
        for name in missing:
            errors[name].append(str(rel_path))

# Print results
if errors:
    print("❌ UNDEFINED NAMES FOUND:\n")
    for name in sorted(errors.keys()):
        print(f"\n'{name}' used in {len(errors[name])} files:")
        for filepath in sorted(errors[name])[:5]:  # Show first 5
            print(f"  - {filepath}")
        if len(errors[name]) > 5:
            print(f"  ... and {len(errors[name]) - 5} more")
else:
    print("✅ No undefined names found!")

print(f"\nTotal issues: {sum(len(v) for v in errors.values())}")
