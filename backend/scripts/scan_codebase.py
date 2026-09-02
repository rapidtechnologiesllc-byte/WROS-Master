#!/usr/bin/env python3
"""
Comprehensive Codebase Scanner
Runs the code gate validator against entire backend to identify all issues
"""
import os
import sys
from pathlib import Path
from code_gate_validator import CodeGateValidator

# Colors
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def scan_directory(directory: str) -> dict:
    """Scan entire directory for code issues."""
    validator = CodeGateValidator()
    results = {
        'total_files': 0,
        'files_scanned': 0,
        'files_with_issues': 0,
        'total_issues': 0,
        'critical_count': 0,
        'high_count': 0,
        'medium_count': 0,
        'low_count': 0,
        'issues_by_type': {},
        'files_breakdown': []
    }

    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip test directories and __pycache__
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv']]

        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                python_files.append(os.path.join(root, file))

    results['total_files'] = len(python_files)

    print(f"\n{'='*60}")
    print(f"CODEBASE SECURITY SCAN")
    print(f"{'='*60}\n")
    print(f"Scanning {len(python_files)} Python files...\n")

    # Scan each file
    for file_path in sorted(python_files):
        if validator.validate_file(file_path):
            results['files_scanned'] += 1
        else:
            results['files_scanned'] += 1
            results['files_with_issues'] += 1

            # Count issues
            file_issues = {
                'path': file_path,
                'issues': validator.issues,
                'critical': len([i for i in validator.issues if i['severity'] == 'CRITICAL']),
                'high': len([i for i in validator.issues if i['severity'] == 'HIGH']),
                'medium': len([i for i in validator.issues if i['severity'] == 'MEDIUM']),
                'low': len([i for i in validator.issues if i['severity'] == 'LOW'])
            }

            results['files_breakdown'].append(file_issues)
            results['total_issues'] += len(validator.issues)
            results['critical_count'] += file_issues['critical']
            results['high_count'] += file_issues['high']
            results['medium_count'] += file_issues['medium']
            results['low_count'] += file_issues['low']

            # Track issue types
            for issue in validator.issues:
                impact = issue.get('impact_type', 'UNKNOWN')
                if impact not in results['issues_by_type']:
                    results['issues_by_type'][impact] = 0
                results['issues_by_type'][impact] += 1

            # Print progress
            severity_emoji = '🔴' if file_issues['critical'] > 0 else '🟡' if file_issues['high'] > 0 else '🟢'
            rel_path = file_path.replace(directory, '').lstrip('\\/')
            print(f"{severity_emoji} {rel_path}")
            print(f"   {file_issues['critical']} critical, {file_issues['high']} high, {file_issues['medium']} medium, {file_issues['low']} low")

    return results

def print_summary(results: dict):
    """Print comprehensive summary."""
    print(f"\n{'='*60}")
    print(f"SCAN RESULTS SUMMARY")
    print(f"{'='*60}\n")

    print(f"Files Scanned: {results['files_scanned']} / {results['total_files']}")
    print(f"Files With Issues: {results['files_with_issues']}")
    print(f"Total Issues Found: {results['total_issues']}\n")

    print(f"Issue Severity Breakdown:")
    print(f"  {RED}🔴 CRITICAL: {results['critical_count']}{RESET}")
    print(f"  {YELLOW}🟡 HIGH: {results['high_count']}{RESET}")
    print(f"  🟠 MEDIUM: {results['medium_count']}")
    print(f"  🟢 LOW: {results['low_count']}\n")

    if results['issues_by_type']:
        print(f"Issues by Type:")
        for issue_type, count in sorted(results['issues_by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {issue_type}: {count}")

    print(f"\n{'='*60}")
    print(f"TOP ISSUES REQUIRING ATTENTION")
    print(f"{'='*60}\n")

    # Sort files by critical count
    critical_files = sorted(
        [f for f in results['files_breakdown'] if f['critical'] > 0],
        key=lambda x: x['critical'],
        reverse=True
    )

    if critical_files:
        for file_info in critical_files[:10]:  # Top 10
            rel_path = file_info['path'].replace(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '').lstrip('\\/')
            print(f"{RED}🔴 {rel_path}{RESET}")
            print(f"   {file_info['critical']} CRITICAL issues:\n")

            for issue in [i for i in file_info['issues'] if i['severity'] == 'CRITICAL'][:3]:
                print(f"   • Line {issue['line']}: {issue['issue']}")
                impact = issue.get('impact_type')
                if impact:
                    print(f"     Impact: {impact}")
            print()
    else:
        print("✅ No critical issues found!\n")

def print_detailed_report(results: dict):
    """Print detailed report for each file."""
    print(f"\n{'='*60}")
    print(f"DETAILED ISSUE REPORT")
    print(f"{'='*60}\n")

    for file_info in sorted(results['files_breakdown'], key=lambda x: x['critical'], reverse=True):
        if not file_info['issues']:
            continue

        rel_path = file_info['path'].replace(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '').lstrip('\\/')
        print(f"\n{BOLD}{rel_path}{RESET}")
        print(f"Issues: {file_info['critical']} critical, {file_info['high']} high, {file_info['medium']} medium, {file_info['low']} low\n")

        for idx, issue in enumerate(file_info['issues'], 1):
            severity_color = RED if issue['severity'] == 'CRITICAL' else YELLOW if issue['severity'] == 'HIGH' else ''
            print(f"{severity_color}{idx}. {issue['severity']}: {issue['issue']}{RESET}")
            print(f"   Line {issue['line']}: {issue['fix']}")

            impact = issue.get('impact_type')
            if impact:
                print(f"   Impact Type: {impact}")
            print()

if __name__ == '__main__':
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    results = scan_directory(backend_dir)
    print_summary(results)

    # Ask if user wants detailed report
    if results['files_with_issues'] > 0:
        print("\n" + "="*60)
        print("Run with --detailed flag to see full report:")
        print("python scan_codebase.py --detailed")
        print("="*60)

        if '--detailed' in sys.argv:
            print_detailed_report(results)
