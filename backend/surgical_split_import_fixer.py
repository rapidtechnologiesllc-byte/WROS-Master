#!/usr/bin/env python3
"""
SURGICAL SPLIT IMPORT FIXER
Fixes split imports where a line with "import (" is followed by a "from" line.

Pattern to fix:
from fastapi import Request
  from app.services.foo import (
    Bar,
    Baz,
  )

Fixed to:
  from fastapi import Request
  from app.services.foo import (
    Bar,
    Baz,
  )
"""

import re
import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BACKEND_DIR = Path(__file__).parent

def fix_split_imports(filepath):
    """Fix split imports in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return False, None

    fixed = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line ends with "import ("
        if 'import (' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()

            # If next line starts with "from", it's a split import
            if next_line.startswith('from '):
                # Extract the split import that was inserted
                split_import = next_line

                # Remove the split import line
                lines.pop(i + 1)

                # Find the closing parenthesis of the multi-line import
                close_paren_idx = None
                for j in range(i + 1, min(i + 20, len(lines))):
                    if ')' in lines[j]:
                        close_paren_idx = j
                        break

                if close_paren_idx is not None:
                    # Insert the split import before the multi-line import
                    lines.insert(i, split_import + '\n')
                    fixed = True
                    i += 1  # Skip past the inserted line
                    continue

        i += 1

    if fixed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True, lines

    return False, None

# Scan and fix all files
print("\n" + "="*70)
print("SURGICAL SPLIT IMPORT FIXER")
print("="*70 + "\n")

files_to_fix = [
    'app/api/v1/endpoints/agent_pyramid_reporting.py',
    'app/api/v1/endpoints/autonomous_job_management.py',
    'app/api/v1/endpoints/bulk_engagement.py',
    'app/api/v1/endpoints/candidate_ranking.py',
    'app/api/v1/endpoints/candidate_rejection.py',
    'app/api/v1/endpoints/candidates.py',
    'app/api/v1/endpoints/checklists.py',
    'app/api/v1/endpoints/employees.py',
    'app/api/v1/endpoints/hiring_manager_validation.py',
    'app/api/v1/endpoints/interview_decision.py',
    'app/api/v1/endpoints/invoices_s316.py',
    'app/api/v1/endpoints/mfa.py',
    'app/api/v1/endpoints/offer_letters.py',
    'app/api/v1/endpoints/pipeline_orchestration.py',
    'app/api/v1/endpoints/portal_messages.py',
    'app/api/v1/endpoints/revenue_target.py',
    'app/api/v1/endpoints/teams.py',
    'app/api/v1/endpoints/user_groups.py',
    'app/core/dependency_injection.py',
    'app/services/ai_message_parser.py',
    'app/services/demand_confirmation_service.py',
    'app/services/employee_service.py',
    'app/services/flash_service.py',
    'app/services/hiring_manager_validation_service.py',
    'app/services/partner_reporting_service.py',
    'app/services/revenue_target_service.py',
    'app/services/skill_assessment_service.py',
    'app/services/whatsapp_engagement_service.py',
    'app/services/workflow_automation_service.py',
]

fixed_count = 0
for file_rel in files_to_fix:
    file_path = BACKEND_DIR / file_rel
    if file_path.exists():
        was_fixed, _ = fix_split_imports(file_path)
        if was_fixed:
            print(f"✅ FIXED: {file_rel}")
            fixed_count += 1
        else:
            print(f"⏭️  SKIP: {file_rel}")
    else:
        print(f"❌ NOT FOUND: {file_rel}")

print(f"\n" + "="*70)
print(f"Fixed {fixed_count}/{len(files_to_fix)} files")
print("="*70 + "\n")

# Validate
print("🧪 Validating imports...")
try:
    import app.main
    print("✅ SUCCESS: Backend imports now working!")
except SyntaxError as e:
    print(f"❌ SyntaxError in {e.filename}:{e.lineno}")
    print(f"   {e.msg}")
except Exception as e:
    print(f"⚠️  Runtime error (not syntax): {type(e).__name__}")
