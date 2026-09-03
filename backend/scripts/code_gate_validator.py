#!/usr/bin/env python3
"""
Code Review Gate Validator
Blocks commits if code violates architectural standards
Used as pre-commit hook
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

        # Skip validation for utility/script files (not API endpoints)
        if 'scripts/' in self.file_path or 'utils/' in self.file_path or 'core/' in self.file_path:
            return

        for i, line in enumerate(self.lines, 1):
            # CRITICAL 1: Missing role template permission check on protected endpoint
            if '@router.get' in line or '@router.post' in line or '@router.put' in line or '@router.delete' in line:
                # Check if endpoint has public marker
                if 'public' in self.lines[i]:
                    continue

                # Look at decorator and next lines for permission enforcement
                decorator_block = '\n'.join(self.lines[i:min(i+10, len(self.lines))])

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
            if 'await' in line and '.catch' not in '\n'.join(self.lines[i:min(i+3, len(self.lines))]):
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

def main():
    """Validate all staged files."""
    print("\n" + "="*60)
    print("CODE REVIEW GATE - PRE-COMMIT VALIDATION")
    print("="*60 + "\n")

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
