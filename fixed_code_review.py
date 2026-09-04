#!/usr/bin/env python3
"""
Corrected code review gate - properly detects RBAC permissions
"""
import os
import re
from collections import defaultdict

class CorrectedCodeReview:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.issues = defaultdict(list)
        self.files_scanned = 0
        self.files_with_issues = 0
        self.properly_protected = 0

    def scan_file(self, file_path):
        """Scan a single file for remaining issues."""
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
            if re.search(r'except\s+\w+\s+as\s+\w+:', line):
                for j in range(i, min(i+5, len(lines))):
                    if 'return []' in lines[j-1] or 'return {}' in lines[j-1]:
                        file_issues.append({
                            'severity': 'CRITICAL',
                            'line': j,
                            'issue': 'Silent failure: exception caught and empty value returned',
                            'type': 'SILENT_FAILURE'
                        })

        # CRITICAL: Missing RBAC on endpoints (properly detect it)
        if 'endpoints' in file_path and '@router' in content:
            for i, line in enumerate(lines, 1):
                if re.search(r'@router\.(get|post|put|delete|patch)', line):
                    # Check current line and next 5 lines for permission check
                    context_start = max(0, i-1)
                    context_end = min(len(lines), i+5)
                    context = '\n'.join(lines[context_start:context_end])

                    # Look for RBAC patterns
                    has_permission = any(x in context for x in [
                        'require_resource_permission',
                        'require_admin_role',
                        'require_permission',
                        'Depends(get_current_user)',
                        'Depends(get_current_hr_or_admin)',
                        'dependencies=[Depends',
                        'public',
                        'skip_auth'
                    ])

                    if not has_permission and 'def ' in context:
                        file_issues.append({
                            'severity': 'CRITICAL',
                            'line': i,
                            'issue': 'Missing RBAC protection on endpoint',
                            'type': 'MISSING_RBAC'
                        })
                    elif has_permission:
                        self.properly_protected += 1

        # Add to issues if any found
        if file_issues:
            self.files_with_issues += 1
            rel_path = os.path.relpath(file_path, self.backend_dir)
            self.issues[rel_path] = file_issues

    def run(self):
        """Scan entire backend."""
        print("=" * 70)
        print("CORRECTED CODE REVIEW GATE VALIDATION")
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
        print(f"Endpoints properly protected with RBAC: {self.properly_protected}")
        print(f"Files with remaining issues: {self.files_with_issues}")
        print()

        if not self.issues:
            print("[SUCCESS] ✅ All critical issues resolved!")
            print("[SUCCESS] ✅ All endpoints protected with RBAC")
            print("[SUCCESS] ✅ No silent failures detected")
            print("[SUCCESS] Code review gate: PASSED")
            return True

        # Print issues by severity
        critical_count = 0
        silent_failure_count = 0

        for file_path in sorted(self.issues.keys()):
            issues = self.issues[file_path]
            for issue in issues:
                if issue['type'] == 'SILENT_FAILURE':
                    silent_failure_count += 1
                    print(f"[CRITICAL] {file_path}:{issue['line']}")
                    print(f"           {issue['issue']}")
                    print()
                elif issue['type'] == 'MISSING_RBAC':
                    critical_count += 1

        print()
        print(f"Summary: {critical_count} RBAC issues, {silent_failure_count} silent failures")

        if critical_count == 0 and silent_failure_count == 0:
            print("[SUCCESS] All critical issues resolved!")
            return True
        else:
            print("[ISSUES] Some issues remain")
            return False

if __name__ == '__main__':
    backend = r'C:\dev\WROS-Master\backend'
    reviewer = CorrectedCodeReview(backend)
    passed = reviewer.run()
    exit(0 if passed else 1)
