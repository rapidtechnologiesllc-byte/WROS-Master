#!/usr/bin/env python3
"""Clean up interviews.py by removing corrupted emoji and fixing f-strings."""

filepath = 'app/api/v1/endpoints/interviews.py'

with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

fixed_lines = []
for i, line in enumerate(lines):
    # Line 586: Remove emoji from Start line
    if 'Start:' in line and 'reminder' not in line and 'strong' in line:
        line = line.replace('âš¡ ', '').replace('Start:</strong>', 'Start:</strong>')

    # Line 587: Remove emoji from End line
    if 'End:' in line and 'strong' in line and 'reminder' not in line:
        line = line.replace('ðŸ• ', '')

    # Line 588: Fix Meeting Link line
    if 'Meeting Link' in line and 'strong' in line:
        line = line.replace('ðŸ"- ', '').replace('+ (f"ðŸ"- ', '+ (f"')

    fixed_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print('✅ Cleaned up interviews.py')
