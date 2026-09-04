"""
Test discovery and validation utilities.

This module helps discover, validate, and categorize tests in the test suite.
Run with: python -m pytest backend/tests/test_discovery.py::discover_tests
"""

import os
import pytest
from pathlib import Path
from typing import Dict, List, Set


def discover_test_files(test_dir: str = "tests") -> Dict[str, List[str]]:
    """Discover all test files organized by category.

    Args:
        test_dir: Root test directory

    Returns:
        Dict mapping category to list of test files
    """
    test_root = Path(test_dir)

    categories = {
        "unit": [],
        "integration": [],
        "e2e": [],
        "regression": [],
        "other": [],
    }

    if not test_root.exists():
        print(f"Test directory {test_dir} does not exist")
        return categories

    for test_file in test_root.rglob("test_*.py"):
        relative_path = str(test_file.relative_to(test_root))

        if "integration" in relative_path:
            categories["integration"].append(relative_path)
        elif "e2e" in relative_path:
            categories["e2e"].append(relative_path)
        elif "regression" in relative_path:
            categories["regression"].append(relative_path)
        else:
            categories["unit"].append(relative_path)

    return categories


def count_test_classes_and_functions(test_file: str) -> tuple:
    """Count test classes and functions in a test file.

    Args:
        test_file: Path to test file

    Returns:
        Tuple of (class_count, function_count)
    """
    try:
        with open(test_file, 'r') as f:
            content = f.read()

        class_count = content.count("class Test")
        function_count = content.count("def test_")

        return class_count, function_count
    except Exception as e:
        print(f"Error reading {test_file}: {e}")
        return 0, 0


def validate_test_fixtures(test_file: str) -> Set[str]:
    """Extract fixture names used in a test file.

    Args:
        test_file: Path to test file

    Returns:
        Set of fixture names
    """
    fixtures = set()

    try:
        with open(test_file, 'r') as f:
            for line in f:
                if "def test_" in line and "(" in line:
                    # Extract parameter names from function signature
                    params_str = line.split("(")[1].split(")")[0]
                    for param in params_str.split(","):
                        param = param.strip().split(":")[0].strip()
                        if param and param != "self":
                            fixtures.add(param)
    except Exception as e:
        print(f"Error analyzing {test_file}: {e}")

    return fixtures


def report_test_coverage():
    """Print detailed test coverage report."""
    print("\n" + "="*70)
    print("TEST SUITE DISCOVERY & ANALYSIS")
    print("="*70)

    categories = discover_test_files()

    total_files = 0
    total_tests = 0

    for category, files in categories.items():
        if not files:
            continue

        print(f"\n{category.upper()} TESTS ({len(files)} files):")
        print("-" * 70)

        category_tests = 0
        for test_file in sorted(files):
            classes, functions = count_test_classes_and_functions(test_file)
            test_count = classes + functions
            category_tests += test_count

            # Highlight missing tests
            if test_count == 0:
                print(f"  ⚠ {test_file:50s} - NO TESTS FOUND")
            else:
                print(f"  ✓ {test_file:50s} - {test_count:3d} tests")

        total_tests += category_tests
        total_files += len(files)
        print(f"  → {category.upper()}: {len(files)} files, {category_tests} tests")

    print("\n" + "="*70)
    print(f"TOTAL: {total_files} test files, {total_tests} tests")
    print("="*70)

    return total_files, total_tests


def validate_test_fixtures_usage():
    """Report on fixture usage across test files."""
    print("\n" + "="*70)
    print("TEST FIXTURE USAGE ANALYSIS")
    print("="*70)

    categories = discover_test_files()
    fixture_usage = {}

    for category, files in categories.items():
        for test_file in files:
            fixtures = validate_test_fixtures(test_file)
            for fixture in fixtures:
                if fixture not in fixture_usage:
                    fixture_usage[fixture] = []
                fixture_usage[fixture].append(test_file)

    print("\nFixture Usage Summary:")
    print("-" * 70)

    critical_fixtures = {"db", "client", "session"}
    for fixture in sorted(fixture_usage.keys()):
        files = fixture_usage[fixture]
        usage_count = len(files)
        is_critical = fixture in critical_fixtures

        status = "✓" if is_critical else "○"
        print(f"{status} {fixture:20s} - used in {usage_count:3d} test files")

    return fixture_usage


if __name__ == "__main__":
    # Run when executed directly
    total_files, total_tests = report_test_coverage()
    fixture_usage = validate_test_fixtures_usage()

    # Summary
    print("\n" + "="*70)
    print("ACTIONABLE INSIGHTS")
    print("="*70)
    print(f"""
1. Test Coverage: {total_tests} tests across {total_files} files

2. Critical Fixtures:
   - db: PostgreSQL database session
   - client: FastAPI test client
   - session: Alternative session fixture

3. Next Steps:
   a) Fix any test files with 0 tests (syntax/import errors)
   b) Migrate legacy SQLite tests to PostgreSQL fixtures
   c) Run full suite: pytest backend/tests -v
   d) Generate coverage report: pytest backend/tests --cov=app --cov-report=html
""")
    print("="*70)
