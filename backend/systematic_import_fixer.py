#!/usr/bin/env python3
"""
SYSTEMATIC IMPORT FIXER - Root cause analysis and fix
Uses agentic gate learnings to identify and fix import patterns

Pattern Analysis:
2. Duplicate imports: Same import statement repeated
3. Broken line continuations: "from app.core.database import (" without closing
4. Orphaned lines: Lines that are imports but syntactically broken
"""

import re
import sys
import io
from pathlib import Path
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKEND_DIR = Path(__file__).parent

def detect_malformed_import(line):
    """Detect if a line has a malformed import."""
    if line.count(' import ') > 1:
        return 'DUPLICATE_IMPORT_KEYWORD'

    if 'from app.core' in line and 'import (' in line and ')' not in line:
        return 'UNCLOSED_IMPORT_PAREN'

    if line.strip().startswith('from ') and line.strip().endswith('import ('):
        return 'OPEN_IMPORT_PAREN'

    return None

def fix_python_file(filepath):
    """Fix all import issues in a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return False, []

    fixed_lines = []
    removed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect malformed patterns
        issue = detect_malformed_import(stripped)

        if issue == 'DUPLICATE_IMPORT_KEYWORD':
            # This is a result of broken bulk fixer
            # Extract actual import we need
            match = re.match(r'from\s+(\S+)\s+import\s+from\s+(\S+)\s+import\s+(.+)', stripped)
            if match:
                # Try to fix: use the latter import
                module, imported_module, names = match.groups()
                fixed_line = f"from {imported_module} import {names}\n"
                fixed_lines.append(fixed_line)
                removed_lines.append((i+1, stripped))
            else:
                # Can't parse - skip it
                removed_lines.append((i+1, stripped))
            i += 1
            continue

        if issue == 'UNCLOSED_IMPORT_PAREN':
            # Find closing paren in next lines
            if ')' in ''.join(lines[i:min(i+10, len(lines))]):
                # Collect multi-line import
                import_block = [line]
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    import_block.append(lines[j])
                    j += 1
                if j < len(lines):
                    import_block.append(lines[j])

                # Join and fix
                full_import = ''.join(import_block)
                # Remove malformed parts and keep valid
                full_import = re.sub(r'from\s+\S+\s+import\s+from\s+', 'from ', full_import)
                fixed_lines.append(full_import.rstrip() + '\n')
                i = j + 1
                continue

        # Check for duplicate imports (same line repeated)
        if stripped.startswith('from ') and i > 0:
            prev_stripped = fixed_lines[-1].strip() if fixed_lines else ''
            if prev_stripped == stripped:
                # Skip duplicate
                removed_lines.append((i+1, stripped))
                i += 1
                continue

        # Keep good lines
        fixed_lines.append(line)
        i += 1

    # Write back
    if removed_lines or len(fixed_lines) != len(lines):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(fixed_lines)
            return True, removed_lines
        except:
            return False, []

    return False, []

# Main scan
print("\n" + "="*70)
print("SYSTEMATIC IMPORT FIXER - Root Cause Analysis")
print("="*70 + "\n")

total_files = 0
fixed_files = 0
total_removed = 0
issues_by_type = defaultdict(list)

for pyfile in sorted(BACKEND_DIR.rglob("*.py")):
    if '__pycache__' in str(pyfile) or '.git' in str(pyfile):
        continue

    total_files += 1
    was_fixed, removed = fix_python_file(pyfile)

    if was_fixed or removed:
        rel_path = str(pyfile.relative_to(BACKEND_DIR.parent.parent))
        if was_fixed:
            fixed_files += 1
            print(f"✅ FIXED: {rel_path} ({len(removed)} lines removed)")
            for line_no, line_text in removed:
                print(f"   - Line {line_no}: {line_text[:60]}...")
                total_removed += len(removed)
        elif removed:
            print(f"⚠️  SKIPPED: {rel_path} (couldn't parse - manual review needed)")

print(f"\n" + "="*70)
print(f"Results:")
print(f"  Total files scanned: {total_files}")
print(f"  Files fixed: {fixed_files}")
print(f"  Lines removed: {total_removed}")
print("="*70 + "\n")

# Final validation
print("🧪 Validating fix...\n")
try:
    import app.main
    print("✅ SUCCESS: app.main imported without syntax errors!")
except SyntaxError as e:
    print(f"❌ SyntaxError in {e.filename}:{e.lineno}")
    print(f"   {e.msg}")
except Exception as e:
    print(f"⚠️  Runtime error (not syntax): {type(e).__name__}")
    print(f"   This is OK - fix is syntactic, not runtime")
