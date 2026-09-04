#!/usr/bin/env python3
"""
Final comprehensive code review gate validation
Checks entire application for remaining issues across all severity levels
"""
import os
import re
from collections import defaultdict

class FinalCodeReview:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.issues = defaultdict(list)
        self.files_scanned = 0
        self.files_with_issues = 0

    def scan_file(self, file_path):
        """Scan a single file for all remaining issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except:
            return

        self.files_scanned += 1
        file_issues = []

        # CRITICAL: Silent failures (return [] or {} in except)
        for i, line in enumerate(lines, 1):
            if 'except' in line:
                for j in range(i, min(i+5, len(lines))):
                    if 'return []' in lines[j-1] or 'return {}' in lines[j-1] or 'return None' in lines[j-1]:
                        file_issues.append({
                            'severity': 'CRITICAL',
                            'line': j,
                            'issue': 'Silent failure: exception caught and empty value returned',
                            'type': 'SILENT_FAILURE'
                        })

        # CRITICAL: Missing permission checks on endpoints
        if 'endpoints' in file_path and '@router' in content:
            for i, line in enumerate(lines, 1):
                if re.search(r'@router\.(get|post|put|delete)', line):
                    # Check next 15 lines for permission check
                    context = '\n'.join(lines[i:min(i+15, len(lines))])
                    has_permission = any(x in context for x in [
                        'require_resource_permission',
                        'require_admin_role',
                        'require_permission',
                        'Depends(get_current_user)',
                        'public'
                    ])
                    if not has_permission and 'def ' in context:
                        file_issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Missing permission check on protected endpoint',
                            'type': 'MISSING_PERMISSION'
                        })

        # HIGH: Missing error logging in except blocks
        for i, line in enumerate(lines, 1):
            if 'except' in line and ':' in line:
                for j in range(i, min(i+5, len(lines))):
                    next_line = lines[j-1] if j > 0 else ''
                    if 'raise' not in next_line and 'logger' not in next_line and next_line.strip():
                        if 'except' not in next_line:
                            file_issues.append({
                                'severity': 'HIGH',
                                'line': j,
                                'issue': 'Exception caught without logging or raising',
                                'type': 'MISSING_ERROR_LOG'
                            })
                            break

        # HIGH: Bare except clauses
        if re.search(r'except\s*:', content):
            for i, line in enumerate(lines, 1):
                if re.search(r'except\s*:', line):
                    file_issues.append({
                        'severity': 'HIGH',
                        'line': i,
                        'issue': 'Bare except clause - must specify exception type',
                        'type': 'BARE_EXCEPT'
                    })

        # Add to issues if any found
        if file_issues:
            self.files_with_issues += 1
            rel_path = os.path.relpath(file_path, self.backend_dir)
            self.issues[rel_path] = file_issues

    def run(self):
        """Scan entire backend."""
        print("=" * 70)
        print("FINAL CODE REVIEW GATE VALIDATION")
        print("=" * 70)
        print()

        for root, dirs, files in os.walk(self.backend_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', 'env']]

            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    self.scan_file(file_path)

        # Print summary
        print(f"Files scanned: {self.files_scanned}")
        print(f"Files with issues: {self.files_with_issues}")
        print()

        if not self.issues:
            print("[OK] No critical or high-severity issues found!")
            print("[OK] Code review gate: PASSED")
            return True

        # Print issues by severity
        critical_count = 0
        high_count = 0

        for file_path in sorted(self.issues.keys()):
            issues = self.issues[file_path]
            for issue in issues:
                if issue['severity'] == 'CRITICAL':
                    critical_count += 1
                    print(f"[CRITICAL] {file_path}:{issue['line']}")
                    print(f"           {issue['issue']}")
                    print()
                elif issue['severity'] == 'HIGH':
                    high_count += 1

        if high_count > 0:
            print(f"[HIGH] Found {high_count} high-severity issues")

        print()
        print(f"Summary: {critical_count} CRITICAL, {high_count} HIGH issues remaining")

        if critical_count == 0 and high_count == 0:
            print("[OK] All critical and high-severity issues resolved!")
            return True
        else:
            print("[FAIL] Code review gate: Issues remain")
            return False

    def print_detailed_report(self):
        """Print detailed report with fixes."""
        print()
        print("=" * 70)
        print("DETAILED ISSUE REPORT")
        print("=" * 70)
        print()

        for file_path in sorted(self.issues.keys()):
            issues = self.issues[file_path]
            print(f"File: {file_path}")
            for issue in issues:
                print(f"  Line {issue['line']}: [{issue['severity']}] {issue['issue']}")
                print(f"  Type: {issue['type']}")
            print()

if __name__ == '__main__':
    backend = r'C:\dev\WROS-Master\backend'
    reviewer = FinalCodeReview(backend)
    passed = reviewer.run()
    reviewer.print_detailed_report()

    if passed:
        print("[SUCCESS] Code review gate validation complete - Application is clean!")
        exit(0)
    else:
        print("[FAILURE] Code review gate found remaining issues")
        exit(1)
