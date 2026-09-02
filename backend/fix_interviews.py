#!/usr/bin/env python3
import logging
"""Fix malformed f-strings in interviews.py."""

import re

filepath = 'app/api/v1/endpoints/interviews.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
for line in lines:
    # Fix patterns like: f"...--" word -> f"...-- word"
    if '--"' in line and 'f"' in line:
        line = line.replace('--" ', '-- ')
    fixed_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('Fixed interviews.py')
