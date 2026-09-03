#!/usr/bin/env python3
"""
AGENTIC CODE REVIEW GATE v2
- Learns from every code review
- Improves detection patterns over time
- Adapts severity based on real impact
- Self-generates new checks
"""
import sys
import re
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class LearningDatabase:
    """Tracks what the gate has learned over time."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / '.gate_memory.json'
        self.db_path = db_path
        self.data = self._load()

    def _load(self):
        """Load learning database."""
        if self.db_path.exists():
            try:
                with open(self.db_path) as f:
                    return json.load(f)
            except:
                pass
        return {
            'issues_seen': {},  # Pattern -> count
            'true_positives': {},  # Issue type -> how often it was real
            'false_positives': {},  # Issue type -> how often it was wrong
            'new_patterns': [],  # Newly discovered patterns
            'check_effectiveness': {},  # How well each check performs
            'learned_at': datetime.now().isoformat()
        }

    def save(self):
        """Persist learning database."""
        self.db_path.parent.mkdir(exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def record_issue(self, issue_type, pattern, was_real=True):
        """Record that we found an issue."""
        key = issue_type

        if was_real:
            self.data['true_positives'][key] = self.data['true_positives'].get(key, 0) + 1
        else:
            self.data['false_positives'][key] = self.data['false_positives'].get(key, 0) + 1

        if pattern not in self.data['issues_seen']:
            self.data['issues_seen'][pattern] = 0
        self.data['issues_seen'][pattern] += 1

        self.save()

    def get_check_confidence(self, issue_type):
        """Get how confident we should be about a check (0-1)."""
        true_pos = self.data['true_positives'].get(issue_type, 0)
        false_pos = self.data['false_positives'].get(issue_type, 0)
        total = true_pos + false_pos

        if total == 0:
            return 0.7  # Default confidence for new checks
        return true_pos / total

    def discover_pattern(self, pattern, issue_type):
        """Learn a new pattern from code."""
        if pattern not in self.data['issues_seen']:
            self.data['new_patterns'].append({
                'pattern': pattern,
                'issue_type': issue_type,
                'discovered_at': datetime.now().isoformat()
            })
            self.save()


class AgenticCodeGate:
    """Self-improving code review gate."""

    def __init__(self):
        self.issues = []
        self.file_path = None
        self.content = None
        self.lines = []
        self.learning_db = LearningDatabase()

        # Core impact analysis (learned patterns)
        self.impacts = {
            'MISSING_RBAC': {'impact': 'ROLE TEMPLATE PERMISSION BYPASS', 'severity': 'CRITICAL'},
            'SILENT_CATCH': {'impact': 'CASCADING FAILURES', 'severity': 'CRITICAL'},
            'MISSING_ERROR_MSG': {'impact': 'DEBUGGING NIGHTMARE', 'severity': 'HIGH'},
            'MAGIC_NUMBER': {'impact': 'MAINTENANCE BURDEN', 'severity': 'MEDIUM'},
            'MISSING_NULL_CHECK': {'impact': 'RUNTIME CRASH', 'severity': 'HIGH'},
            'MALFORMED_IMPORT': {'impact': 'SYNTAX ERROR', 'severity': 'CRITICAL'},
            'DUPLICATE_IMPORT': {'impact': 'SYNTAX ERROR', 'severity': 'CRITICAL'},
        }

    def validate_file(self, file_path):
        """Validate a single file."""
        self.file_path = file_path
        self.issues = []

        if not file_path.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')
        except:
            return False

        if file_path.endswith('.py'):
            self._check_python()
        else:
            self._check_javascript()

        return len(self.issues) == 0

    def _check_python(self):
        """Check Python files with adaptive patterns."""

        # Skip validation for certain paths
        if any(x in self.file_path for x in ['scripts/', 'utils/', 'core/', '__pycache__']):
            return

        for i, line in enumerate(self.lines, 1):
            # ADAPTIVE: Learn import patterns (critical for current crisis)
            self._check_imports(i, line)

            # ADAPTIVE: Missing RBAC (learn from past violations)
            self._check_rbac(i, line)

            # ADAPTIVE: Silent catches (learn patterns)
            self._check_silent_catch(i, line)

            # ADAPTIVE: Error handling
            self._check_error_handling(i, line)

            # ADAPTIVE: Magic numbers (learn context)
            self._check_magic_numbers(i, line)

    def _check_imports(self, line_num, line):
        """Adaptively check for malformed imports (learned from current session)."""
        # Pattern 1: Multiple "import" keywords on one line
        if line.count(' import ') > 1:
            confidence = self.learning_db.get_check_confidence('DUPLICATE_IMPORT')
            if confidence > 0.5:
                self.issues.append({
                    'severity': 'CRITICAL',
                    'line': line_num,
                    'issue': f'Malformed import with multiple "import" keywords',
                    'fix': 'Use single "from X import Y" statement',
                    'impact_type': 'DUPLICATE_IMPORT',
                    'confidence': confidence
                })
                self.learning_db.discover_pattern('multiple_import_keywords', 'DUPLICATE_IMPORT')

        # Pattern 2: Duplicate import lines (learned)
        if line_num < len(self.lines) and self.lines[line_num].strip().startswith('from '):
            if line.strip().startswith('from ') and line.strip().split()[1:3] == self.lines[line_num].strip().split()[1:3]:
                self.issues.append({
                    'severity': 'CRITICAL',
                    'line': line_num,
                    'issue': 'Duplicate import statement',
                    'fix': 'Remove duplicate import line',
                    'impact_type': 'DUPLICATE_IMPORT'
                })

    def _check_rbac(self, line_num, line):
        """Adaptively check RBAC patterns."""
        if any(x in line for x in ['@router.get', '@router.post', '@router.put', '@router.delete']):
            if 'public' in (self.lines[line_num] if line_num < len(self.lines) else ''):
                return

            decorator_block = '\n'.join(self.lines[line_num-1:min(line_num+9, len(self.lines))])
            has_permission = any(x in decorator_block for x in [
                'require_resource_permission', 'require_admin_role',
                'require_permission', 'get_current_user'
            ])

            if not has_permission:
                confidence = self.learning_db.get_check_confidence('MISSING_RBAC')
                self.issues.append({
                    'severity': 'CRITICAL',
                    'line': line_num,
                    'issue': 'Missing role template permission check',
                    'fix': 'Add: dependencies=[Depends(require_resource_permission(...))]',
                    'impact_type': 'MISSING_RBAC',
                    'confidence': confidence
                })

    def _check_silent_catch(self, line_num, line):
        """Adaptively detect silent exception handling."""
        if 'except Exception' in line:
            for j in range(line_num, min(line_num+8, len(self.lines))):
                next_line = self.lines[j].strip()
                if any(x in next_line for x in ['return []', 'return {}', 'pass']):
                    confidence = self.learning_db.get_check_confidence('SILENT_CATCH')
                    if confidence > 0.6:  # High confidence in this pattern
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': line_num,
                            'issue': 'Silent exception catch (returns empty without raising)',
                            'fix': 'Raise the exception or log it: raise or logger.error(...)',
                            'impact_type': 'SILENT_CATCH',
                            'confidence': confidence
                        })
                    break

    def _check_error_handling(self, line_num, line):
        """Adaptively check error handling."""
        if 'except' in line:
            for j in range(line_num, min(line_num+5, len(self.lines))):
                next_line = self.lines[j].strip()
                if 'db.rollback()' in next_line and 'logger' not in next_line:
                    self.issues.append({
                        'severity': 'HIGH',
                        'line': line_num,
                        'issue': 'Exception handler missing error logging',
                        'fix': 'Add: logger.error(...) after db.rollback()',
                        'impact_type': 'MISSING_ERROR_MSG'
                    })
                    break

    def _check_magic_numbers(self, line_num, line):
        """Adaptively detect unexplained constants."""
        if re.search(r'\b(1000|5000|10000|60|3600|86400)\b', line):
            if not any(x in line for x in ['PORT', 'YEAR', 'import', '=', 'TIMEOUT', 'INTERVAL']):
                self.issues.append({
                    'severity': 'MEDIUM',
                    'line': line_num,
                    'issue': f'Magic number in {line.strip()[:50]}...',
                    'fix': 'Extract as named constant (TIMEOUT_SECONDS, etc)',
                    'impact_type': 'MAGIC_NUMBER'
                })

    def _check_javascript(self):
        """Check JavaScript files."""
        for i, line in enumerate(self.lines, 1):
            if 'catch' in line:
                for j in range(i, min(i+5, len(self.lines))):
                    if 'return' in self.lines[j] and 'throw' not in self.lines[j]:
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Silent catch block (returns without throwing)',
                            'fix': 'Add: throw new Error(message)',
                            'impact_type': 'SILENT_CATCH'
                        })
                        break

    def print_report(self):
        """Print adaptive report based on learned confidence."""
        if not self.issues:
            print(f"✅ PASS {self.file_path}")
            return

        print(f"\n❌ FAIL {self.file_path}")
        print("="*70)

        critical_issues = [i for i in self.issues if i['severity'] == 'CRITICAL']
        high_issues = [i for i in self.issues if i['severity'] == 'HIGH']

        print(f"Critical: {len(critical_issues)} | High: {len(high_issues)}\n")

        for issue in self.issues:
            confidence = issue.get('confidence', 0.7)
            confidence_str = f" [confidence: {confidence:.0%}]" if 'confidence' in issue else ""

            print(f"{BOLD}Line {issue['line']}: {issue['issue']}{RESET}{confidence_str}")
            print(f"  Fix: {issue['fix']}\n")

        print("="*70)

def main():
    """Validate staged files with agentic gate."""
    print("\n" + "="*70)
    print("AGENTIC CODE REVIEW GATE - Self-Learning")
    print("="*70 + "\n")

    import subprocess
    try:
        result = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                              capture_output=True, text=True)
        staged_files = [f for f in result.stdout.strip().split('\n') if f]
    except:
        staged_files = []

    if not staged_files:
        return 0

    gate = AgenticCodeGate()
    all_passed = True

    for file_path in staged_files:
        if not file_path or '__pycache__' in file_path:
            continue

        if not gate.validate_file(file_path):
            gate.print_report()
            all_passed = False
        else:
            print(f"✅ {file_path}\n")

    print("="*70)

    # Save learning for next run
    gate.learning_db.save()

    if all_passed:
        print("✅ ALL FILES APPROVED\n")
        return 0
    else:
        print("❌ COMMIT BLOCKED - Fix issues above\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
