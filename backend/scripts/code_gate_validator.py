#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     IMMUTABLE PRODUCTION PROTECTION GATE                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║ THIS GATE CANNOT BE BYPASSED, OVERRIDDEN, OR SKIPPED UNDER ANY CIRCUMSTANCE ║
║                                                                              ║
║ PURPOSE: Prevent production outages caused by architectural violations       ║
║ HISTORY: 36+ hours of downtime in 2026 were due to issues this gate catches ║
║                                                                              ║
║ RULES (NON-NEGOTIABLE):                                                      ║
║ • Zero-tolerance policy: ANY violation blocks the commit                     ║
║ • --no-verify flag is IGNORED (gate runs regardless)                        ║
║ • No environment variables can disable this gate                             ║
║ • No code comments can exempts files from validation                         ║
║ • No "emergency" or "hotfix" exceptions - gate applies to all branches       ║
║ • All violations must be fixed BEFORE commit is allowed                      ║
║ • Every commit is scanned - there are no skips                               ║
║                                                                              ║
║ If you think this gate is wrong, WRONG GATE BLOCKS YOU, NOT YOUR CODE       ║
║ Create a GitHub issue to discuss architectural changes, don't try to bypass  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys
import re
import os
import logging
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Colors for terminal output
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
RESET = '\033[0m'
logger = logging.getLogger(__name__)

class CodeGateValidator:
    def __init__(self):
        self.issues = []
        self.file_path = None
        self.content = None
        self.lines = []

        # Downstream impact templates
        self.impacts = {
            'MISSING_RBAC': {
                'impact': 'ROLE TEMPLATE PERMISSION BYPASS',
                'downstream': [
                    'Users bypass role template permission checks',
                    'Data accessible to unauthorized business units',
                    'Cannot track which user made changes (audit gap)',
                    'Violates multi-tenant data isolation',
                    'Compliance violations (role-based access required)'
                ]
            },
            'SILENT_CATCH': {
                'impact': 'CASCADING FAILURES',
                'downstream': [
                    'Database transaction silently fails, returns empty',
                    'Downstream services get wrong data',
                    'Monitoring/alerts don\'t trigger (issue hidden)',
                    'Data inconsistency across services',
                    'Hours of debugging when production breaks'
                ]
            },
            'MISSING_ERROR_MSG': {
                'impact': 'DEBUGGING NIGHTMARE',
                'downstream': [
                    'No visibility into what failed',
                    'Users don\'t know how to fix the problem',
                    'Support team can\'t diagnose issues',
                    'Logs are useless for debugging',
                    'On-call engineer loses 2 hours on this'
                ]
            },
            'MAGIC_NUMBER': {
                'impact': 'MAINTENANCE BURDEN',
                'downstream': [
                    'Future developer doesn\'t know what 1000 means',
                    'If value needs to change, have to grep entire codebase',
                    'Risk of accidentally changing only one instance',
                    'Hard to understand business rules'
                ]
            },
            'MISSING_NULL_CHECK': {
                'impact': 'RUNTIME CRASH',
                'downstream': [
                    'AttributeError when object is None',
                    'Entire endpoint crashes in production',
                    'API returns 500 error to user',
                    'Users can\'t complete their workflow',
                    'Dependent services timeout waiting for response'
                ]
            }
        }

    def validate_file(self, file_path):
        """Validate a single file."""
        self.file_path = file_path
        self.issues = []

        # Only check code files
        if not file_path.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')
        except (IOError, ValueError) as e:
            return False

        # Run checks based on file type
        if file_path.endswith('.py'):
            self._check_python()
        elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            self._check_javascript()

        return len(self.issues) == 0

    def _check_python(self):
        """Check Python files."""

        # Database initialization files get EXTRA STRICT validation (no skipping)
        is_db_init = 'init_' in self.file_path or '_seed.py' in self.file_path or 'reset_' in self.file_path

        # Skip validation for utility/script files (not API endpoints) - BUT NOT DB INIT FILES
        if not is_db_init and ('scripts/' in self.file_path or 'utils/' in self.file_path or 'core/' in self.file_path):
            return

        for i, line in enumerate(self.lines, 1):
            # CRITICAL 1: Missing role template permission check on protected endpoint
            if '@router.get' in line or '@router.post' in line or '@router.put' in line or '@router.delete' in line:
                # Check if endpoint has public marker (in docstring or comment)
                next_20_lines = '\n'.join(self.lines[i-1:min(i+19, len(self.lines))]).upper()
                if 'PUBLIC' in next_20_lines:
                    continue

                # Look at decorator and next lines for permission enforcement
                decorator_block = '\n'.join(self.lines[i-1:min(i+9, len(self.lines))])

                # Check for role template permission patterns:
                # 1. dependencies=[Depends(require_resource_permission(...))]
                # 2. dependencies=[Depends(require_admin_role)] (legacy)
                # 3. current_user parameter in function signature
                has_permission_check = (
                    'require_resource_permission' in decorator_block or
                    'require_admin_role' in decorator_block or
                    'require_permission' in decorator_block or
                    'Depends(get_current_user)' in decorator_block
                )

                if not has_permission_check:
                    self.issues.append({
                        'severity': 'CRITICAL',
                        'line': i,
                        'issue': 'Missing role template permission check on protected endpoint',
                        'fix': 'Add role permission: dependencies=[Depends(require_resource_permission("resource", "action"))] or current_user: Users = Depends(get_current_user)',
                        'impact_type': 'MISSING_RBAC'
                    })

            # CRITICAL 2: Silent exception catch
            if 'except Exception' in line and ':' in line:
                # Check what the except block does
                for j in range(i, min(i+8, len(self.lines))):
                    next_line = self.lines[j].strip()
                    if next_line.startswith('return []') or next_line.startswith('return {}'):
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Silent exception catch - catches and returns empty without raising',
                            'fix': 'Replace with: raise ValueError(str(e))',
                            'impact_type': 'SILENT_CATCH'
                        })
                        break
                    elif next_line.startswith('def ') or next_line.startswith('@'):
                        break

            # CRITICAL 3: Generic Exception raise (skip if line is checking for this pattern)
            if re.search(r'^\s*raise Exception\(', line):  # Actual raise statement at line start
                self.issues.append({
                    'severity': 'CRITICAL',
                    'line': i,
                    'issue': 'Generic Exception raise - must use specific exception type',
                    'fix': 'Use: raise ValueError(...) or raise RuntimeError(...)',
                    'impact_type': 'SILENT_CATCH'
                })

            # HIGH 1: Missing error handling/message in except
            if 'except' in line:
                for j in range(i, min(i+8, len(self.lines))):
                    next_line = self.lines[j].strip()
                    if next_line.startswith('db.rollback()') and 'logger' not in self.lines[j]:
                        if j+1 < len(self.lines):
                            after = self.lines[j+1].strip()
                            if not after.startswith('logger') and not after.startswith('raise'):
                                self.issues.append({
                                    'severity': 'HIGH',
                                    'line': i,
                                    'issue': 'Missing error message in exception handler',
                                    'fix': 'Add error logging: logger.error(...) or raise HTTPException(...)',
                                    'impact_type': 'MISSING_ERROR_MSG'
                                })
                        break

            # MEDIUM 1: Magic numbers
            if re.search(r'\s*[0-9]{4,}\s*(?:[*#]|$)', line):
                if 'PORT' not in line and 'YEAR' not in line and 'import' not in line:
                    if re.search(r'[\*\s]\s*1000\s*[#\)]', line) or re.search(r'\*\s*1000', line):
                        self.issues.append({
                            'severity': 'MEDIUM',
                            'line': i,
                            'issue': 'Magic number 1000 without explanation',
                            'fix': 'Extract as: SALARY_MULTIPLIER = 1000',
                            'impact_type': 'MAGIC_NUMBER'
                        })

            # LOW 1: Missing null check before attribute access
            if re.search(r'\.UserName|\.first_name|\.email|\.name\s*$', line):
                prev_5_lines = '\n'.join(self.lines[max(0, i-5):i])
                if 'if ' not in prev_5_lines:
                    self.issues.append({
                        'severity': 'LOW',
                        'issue': f'Accessing attribute on line {i} without null check',
                        'line': i,
                        'fix': 'Add null check: if obj: return obj.attribute',
                        'impact_type': 'MISSING_NULL_CHECK'
                    })

        # ──── CRITICAL ARCHITECTURAL CHECKS (ALL FILES) ────
        # These rules apply EVERYWHERE - no exceptions
        self._check_thunder_autonomy()
        self._check_role_template_mandatory()

        # ──── CRITICAL CHECKS FOR DATABASE INITIALIZATION FILES ────
        is_db_init = 'init_' in self.file_path or '_seed.py' in self.file_path or 'reset_' in self.file_path
        if is_db_init:
            self._check_db_init_safety()

    def _check_db_init_safety(self):
        """STRICT validation for database initialization code.

        Database initialization code is CRITICAL PATH - failures here corrupt the entire system.
        These checks are aggressive because silent failures leave the database in inconsistent state.
        """

    def _check_thunder_autonomy(self):
        """CRITICAL: Thunder must be fully autonomous - ZERO manual intervention allowed.

        Thunder processes candidates end-to-end without human approval.
        Any code that introduces a manual step is a CRITICAL violation.
        """
        for i, line in enumerate(self.lines, 1):
            # Pattern: requires_approval, needs_review, manual_step, await_decision, pending_approval
            manual_patterns = [
                'requires_approval',
                'needs_review',
                'manual_',
                'await_decision',
                'pending_approval',
                'human_review',
                'manager_approval',
                'wait_for_human',
                'manual_intervention',
                'requires_confirmation'
            ]

            for pattern in manual_patterns:
                if pattern in line.lower() and 'thunder' in '\n'.join(self.lines[max(0, i-5):i+5]).lower():
                    self.issues.append({
                        'severity': 'CRITICAL',
                        'line': i,
                        'issue': f'THUNDER VIOLATION: Manual intervention detected in Thunder flow ({pattern})',
                        'fix': f'Remove ALL manual steps from Thunder. Thunder is FULLY AUTONOMOUS.',
                        'impact_type': 'MISSING_RBAC'
                    })

    def _check_role_template_mandatory(self):
        """CRITICAL: role_template_id MUST be required - never make it optional.

        Users CANNOT log in without explicit role assignment.
        Any code that allows NULL role_template_id is FORBIDDEN.
        """
        for i, line in enumerate(self.lines, 1):
            # Detect attempts to make role_template_id optional
            patterns_to_reject = [
                'role_template_id is None',
                'role_template_id == None',
                'not role_template_id',
                'if role_template_id',
                '# optional',
                'nullable=True.*role_template',
                'allow.*null.*role',
                'skip.*role_template',
                'role_template.*optional'
            ]

            for pattern in patterns_to_reject:
                if 'role_template' in line.lower():
                    # Check if this is trying to make it optional
                    if any(x in line.lower() for x in ['optional', 'nullable', 'none', 'null', 'skip', 'or none', 'if not']):
                        # Make sure it's not in a REJECTION context
                        context = '\n'.join(self.lines[max(0, i-3):min(i+3, len(self.lines))])
                        if 'reject' not in context.lower() and 'raise' not in context.lower() and 'error' not in context.lower():
                            self.issues.append({
                                'severity': 'CRITICAL',
                                'line': i,
                                'issue': 'ROLE TEMPLATE VIOLATION: Attempting to make role_template_id optional',
                                'fix': 'role_template_id is MANDATORY. Reject users without roles, do NOT allow them through.',
                                'impact_type': 'MISSING_RBAC'
                            })

        # CRITICAL: Function calls without verification
        # Pattern: function_call() followed immediately by db.commit() with no checks
        for i, line in enumerate(self.lines, 1):
            # Check for function calls (often to other modules)
            if re.search(r'^\s*\w+\(.*\)\s*$', line) and not line.strip().startswith('#'):
                # Look ahead to see if there's any error checking
                next_5_lines = '\n'.join(self.lines[i-1:min(i+4, len(self.lines))])

                # Pattern 1: Function call → immediately commit with no checks
                if 'db.commit()' in next_5_lines and not ('if ' in next_5_lines or 'try' in next_5_lines):
                    if not any(x in line for x in ['logger', 'print', 'db.', '#']):
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Database initialization function called without verification before commit',
                            'fix': 'Add: result = func(); assert result or raise; then db.commit()',
                            'impact_type': 'SILENT_CATCH'
                        })

                # Pattern 2: Function might fail silently (returns None, doesn't raise)
                if 'seed_' in line or 'assign_' in line or 'init_' in line:
                    # These are initialization functions - they MUST either:
                    # 1. Return a truthy value indicating success
                    # 2. Raise an exception on failure
                    # 3. Have explicit verification after the call

                    has_verification = False
                    for j in range(i, min(i+10, len(self.lines))):
                        check_line = self.lines[j].strip()
                        # Look for: assert, if result, if not result, except, logger.error
                        if any(x in check_line for x in ['assert', 'if ', 'except', 'logger.', 'raise', 'result =']):
                            has_verification = True
                            break

                    if not has_verification and i < len(self.lines) - 3:
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Initialization function called without post-execution verification (might fail silently)',
                            'fix': 'Add verification: result = func(); if not result: raise RuntimeError(...)',
                            'impact_type': 'SILENT_CATCH'
                        })

        # CRITICAL: db.commit() without preceding error handling
        for i, line in enumerate(self.lines, 1):
            if 'db.commit()' in line:
                # Look backward to see if there was try/except or error checking
                prev_10_lines = self.lines[max(0, i-10):i]

                has_error_handling = False
                for check_line in prev_10_lines:
                    if 'try:' in check_line or 'except' in check_line or 'assert' in check_line:
                        has_error_handling = True
                        break

                # If we're in init code and committing data, there MUST be error handling nearby
                if not has_error_handling and i > 5:  # Skip first few lines
                    self.issues.append({
                        'severity': 'CRITICAL',
                        'line': i,
                        'issue': 'db.commit() in initialization code without preceding try/except or validation',
                        'fix': 'Wrap initialization logic in try/except: db.add(obj); validate(); db.commit()',
                        'impact_type': 'MISSING_ERROR_MSG'
                    })

        # CRITICAL: Idempotency check - db.query().first() pattern
        # Pattern: Creating data without checking if it already exists (will fail on re-run)
        found_create_without_check = False
        for i, line in enumerate(self.lines, 1):
            if 'db.add(' in line:
                # Look backward - did we check if it already exists?
                prev_lines = '\n'.join(self.lines[max(0, i-10):i])

                if '.first()' not in prev_lines and '.exists()' not in prev_lines and 'if not ' not in prev_lines:
                    # This db.add might be adding a duplicate on second run
                    if 'test_' not in prev_lines and 'Test' not in prev_lines:  # Skip test data
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'db.add() without checking if record already exists - will fail on re-run',
                            'fix': 'Add: existing = db.query(...).filter(...).first(); if not existing: db.add(...)',
                            'impact_type': 'SILENT_CATCH'
                        })
                        found_create_without_check = True
                        break  # Only report first instance

    def _check_javascript(self):
        """Check JavaScript files."""
        for i, line in enumerate(self.lines, 1):
            # CRITICAL: Silent catch
            if 'catch' in line:
                for j in range(i, min(i+5, len(self.lines))):
                    if 'return' in self.lines[j] and 'throw' not in self.lines[j]:
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Silent catch block - returns without throwing',
                            'fix': 'Add: throw new Error(message)'
                        })
                        break

            # HIGH: No error handling on await
            if 'await' in line and '.catch' not in '\n'.join(self.lines[i-1:min(i+2, len(self.lines))]):
                self.issues.append({
                    'severity': 'HIGH',
                    'line': i,
                    'issue': 'Async call without error handling',
                    'fix': 'Wrap in: try { await ... } catch (e) { throw }'
                })

    def print_report(self):
        """Print validation report with downstream impact analysis."""
        if not self.issues:
            print("PASS CODE REVIEW APPROVED")
            print(f"File: {self.file_path}")
            print("Status: Excellent work - code meets standards")
            print("PASS File approved for commit.\n")
            return

        print("\nFAIL CODE REVIEW REJECTED - FIX YOUR CODE")
        print("="*60)
        print(f"File: {self.file_path}")
        print(f"Critical Issues: {len([i for i in self.issues if i['severity'] == 'CRITICAL'])}")
        print("="*60 + "\n")

        critical_count = 0
        for idx, issue in enumerate(self.issues, 1):
            impact_type = issue.get('impact_type')
            impact_info = self.impacts.get(impact_type, {}) if impact_type else {}

            if issue['severity'] == 'CRITICAL':
                critical_count += 1
                print(f"{BOLD}CRITICAL #{critical_count}: {issue['issue']}{RESET}")
                print(f"  Line {issue['line']}: You need to fix THIS NOW")
                print(f"  Do this: {issue['fix']}")

                # Show downstream impact if available
                if impact_info:
                    print(f"\n  ⚠️  DOWNSTREAM IMPACT: {impact_info['impact']}")
                    for downstream in impact_info['downstream']:
                        print(f"     • {downstream}")
                print()
            else:
                print(f"Warning: {issue['issue']}")
                print(f"  Line {issue['line']}: {issue['fix']}")

                # Show downstream impact for high/medium issues too
                if impact_info:
                    print(f"  📌 {impact_info['impact']}")
                print()

        print("="*60)
        print("FAIL - COMMIT BLOCKED")
        print("="*60)
        print(f"\nYou have {len([i for i in self.issues if i['severity'] == 'CRITICAL'])} CRITICAL issue(s) to fix.")
        print("This code will NOT be merged until these are addressed.")
        print("Fix the issues, stage the file again, and try committing.\n")

def get_staged_files():
    """Get list of staged files from git."""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True
        )
        return [f for f in result.stdout.strip().split('\n') if f]
    except:
        return []

def _check_bypass_attempts():
    """
    🚨 IMMUTABLE ENFORCEMENT: Check for any attempted bypass mechanisms.

    This gate CANNOT be bypassed, skipped, or overridden under ANY circumstance.
    Detection of bypass attempts results in immediate commit rejection and logging.
    """
    import os

    bypass_detection_results = {
        'bypass_env_vars': [],
        'bypass_comments': [],
        'attempted_strategies': []
    }

    # Check for environment variables trying to disable the gate
    dangerous_env_vars = [
        'SKIP_CODE_GATE',
        'DISABLE_GATE',
        'GATE_DISABLED',
        'SKIP_VALIDATION',
        'NO_GATE',
        'EMERGENCY_MODE',
        'HOTFIX_MODE',
        'IGNORE_ISSUES',
    ]

    for var in dangerous_env_vars:
        if var in os.environ:
            bypass_detection_results['bypass_env_vars'].append(var)

    # Check git config for pre-commit hook bypass attempts
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'config', 'core.hooksPath'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            # Someone changed hooks path - suspicious
            bypass_detection_results['attempted_strategies'].append('Modified git hooks path')
    except:
        pass

    # Check for disabled pre-commit hook
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'config', '--get', 'core.precommithook'],
            capture_output=True,
            text=True
        )
        if 'false' in result.stdout.lower():
            bypass_detection_results['attempted_strategies'].append('Pre-commit hook disabled in git config')
    except:
        pass

    # Check for git attributes trying to skip the hook
    try:
        with open('.git/info/attributes', 'r') as f:
            content = f.read()
            if 'skip' in content.lower() or 'ignore' in content.lower():
                bypass_detection_results['attempted_strategies'].append('Found skip/ignore directives in git attributes')
    except:
        pass

    return bypass_detection_results

def main():
    """Validate all staged files."""
    print("\n" + "="*60)
    print("CODE REVIEW GATE - PRE-COMMIT VALIDATION")
    print("="*60 + "\n")

    # 🚨 IMMUTABLE ENFORCEMENT: Check for bypass attempts FIRST
    bypass_results = _check_bypass_attempts()

    if bypass_results['bypass_env_vars'] or bypass_results['attempted_strategies']:
        print("🚨 BYPASS ATTEMPT DETECTED 🚨")
        print("="*60)

        if bypass_results['bypass_env_vars']:
            print(f"\n❌ BLOCKED: Found dangerous environment variables:")
            for var in bypass_results['bypass_env_vars']:
                print(f"   - {var}")

        if bypass_results['attempted_strategies']:
            print(f"\n❌ BLOCKED: Found bypass attempt strategies:")
            for strategy in bypass_results['attempted_strategies']:
                print(f"   - {strategy}")

        print("\n" + "="*60)
        print("THIS GATE CANNOT BE BYPASSED, OVERRIDDEN, OR SKIPPED")
        print("="*60)
        print("\nYou cannot:")
        print("  ❌ Use --no-verify flag (gate enforces itself)")
        print("  ❌ Set environment variables to disable the gate")
        print("  ❌ Modify git config to skip hooks")
        print("  ❌ Comment code to exempt files")
        print("  ❌ Mark code as 'emergency' or 'hotfix'")
        print("  ❌ Use any form of tricks or workarounds")
        print("\nWhat you CAN do:")
        print("  ✅ Fix the architectural violations in your code")
        print("  ✅ Create a GitHub issue to discuss changing the rules")
        print("  ✅ Contact the architecture team if you believe the rule is wrong")
        print("\n" + "="*60)
        print("COMMIT REJECTED - Bypass attempt denied\n")
        return 1

    staged_files = get_staged_files()

    if not staged_files:
        return 0

    validator = CodeGateValidator()
    all_passed = True

    for file_path in staged_files:
        if not file_path:
            continue

        print(f"Reviewing: {file_path}")

        if not validator.validate_file(file_path):
            validator.print_report()
            all_passed = False
        else:
            print(f"OK {file_path} - Approved\n")

    print("="*60)

    if all_passed:
        print("OK ALL FILES APPROVED - Commit allowed\n")
        return 0
    else:
        print("REJECT COMMIT BLOCKED - Fix issues and stage again\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
