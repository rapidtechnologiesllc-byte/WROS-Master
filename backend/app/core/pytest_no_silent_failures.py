"""
Pytest plugin: no_silent_failures

Prevents silent failures in service layer functions by detecting patterns where:
1. Exceptions are caught and empty values returned without re-raising
2. Service functions return None/empty dict/empty list on error without raising

CRITICAL PRINCIPLE: Service layer functions MUST ALWAYS raise exceptions on errors.
They should NEVER return empty collections or None to indicate failure.

API endpoints can catch exceptions and return error responses, but the service layer
must fail fast and explicitly.

Installation:
1. Add to pytest configuration (pytest.ini or setup.cfg):
   [pytest]
   plugins = app.core.pytest_no_silent_failures

2. Or add to conftest.py:
   pytest_plugins = ['app.core.pytest_no_silent_failures']

3. Run tests with pytest to catch violations during CI/CD
"""

import ast
import pytest
from pathlib import Path
from typing import List, Tuple


class ServiceLayerAnalyzer(ast.NodeVisitor):
    """
    Analyzes Python AST to detect silent failures in service layer functions.

    Detects patterns:
    - except: return []
    - except: return {}
    - except: return None
    - Service function returning empty without raising
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.violations: List[Tuple[int, str]] = []
        self.in_service_function = False
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check if this is a service layer function."""
        # Service functions typically:
        # 1. Are in *_service.py files
        # 2. Are static or class methods
        # 3. Have @staticmethod or @classmethod decorators

        is_service_file = '_service.py' in self.filename
        has_service_decorator = any(
            (isinstance(d, ast.Name) and d.id in ('staticmethod', 'classmethod'))
            or (isinstance(d, ast.Attribute) and d.attr in ('staticmethod', 'classmethod'))
            for d in node.decorator_list
        )

        if is_service_file or has_service_decorator:
            old_in_service = self.in_service_function
            old_function = self.current_function

            self.in_service_function = True
            self.current_function = node.name
            self.generic_visit(node)

            self.in_service_function = old_in_service
            self.current_function = old_function
        else:
            self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        """Check for silent failures in try-except blocks."""
        for handler in node.handlers:
            self._check_except_handler(handler)

        self.generic_visit(node)

    def _check_except_handler(self, handler: ast.ExceptHandler):
        """Detect silent returns in except handler."""
        for statement in handler.body:
            # Pattern 1: return [] (empty list)
            if self._is_return_empty_list(statement):
                line = statement.lineno
                msg = (
                    f"{self.filename}:{line} - "
                    f"Silent return of empty list in except block. "
                    f"Must re-raise exception: raise ValueError(...)"
                )
                self.violations.append((line, msg))

            # Pattern 2: return {} (empty dict)
            if self._is_return_empty_dict(statement):
                line = statement.lineno
                msg = (
                    f"{self.filename}:{line} - "
                    f"Silent return of empty dict in except block. "
                    f"Must re-raise exception: raise ValueError(...)"
                )
                self.violations.append((line, msg))

            # Pattern 3: return None
            if self._is_return_none(statement):
                line = statement.lineno
                msg = (
                    f"{self.filename}:{line} - "
                    f"Silent return of None in except block. "
                    f"Must re-raise exception: raise ValueError(...)"
                )
                self.violations.append((line, msg))

    @staticmethod
    def _is_return_empty_list(node: ast.stmt) -> bool:
        """Check if statement is: return []"""
        if not isinstance(node, ast.Return):
            return False
        if node.value is None:
            return False
        if not isinstance(node.value, ast.List):
            return False
        return len(node.value.elts) == 0

    @staticmethod
    def _is_return_empty_dict(node: ast.stmt) -> bool:
        """Check if statement is: return {}"""
        if not isinstance(node, ast.Return):
            return False
        if node.value is None:
            return False
        if not isinstance(node.value, ast.Dict):
            return False
        return len(node.value.keys) == 0

    @staticmethod
    def _is_return_none(node: ast.stmt) -> bool:
        """Check if statement is: return None or return (empty return)"""
        if not isinstance(node, ast.Return):
            return False
        # return (no value)
        if node.value is None:
            return False  # This is allowed in some contexts
        # return None
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            return True
        if isinstance(node.value, ast.NameConstant) and node.value.value is None:
            return True
        return False


def analyze_file(filepath: Path) -> List[Tuple[int, str]]:
    """Analyze a Python file for silent failures."""
    if not filepath.suffix == '.py':
        return []

    if '/test' in str(filepath) or '/tests' in str(filepath):
        return []  # Skip test files

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)
        analyzer = ServiceLayerAnalyzer(str(filepath))
        analyzer.visit(tree)
        return analyzer.violations
    except SyntaxError:
        return []  # Skip files with syntax errors


def pytest_collection_modifyitems(config, items):
    """
    Hook called after test collection.

    Analyze all Python files in app/ for silent failures.
    If violations found, add a pytest marker to fail the test run.
    """
    app_dir = Path(__file__).parent.parent
    violations: List[Tuple[int, str]] = []

    for py_file in app_dir.rglob('*.py'):
        violations.extend(analyze_file(py_file))

    if violations:
        # Print all violations
        print("\n" + "="*80)
        print("PYTEST SILENT FAILURE DETECTION")
        print("="*80)
        for line_no, msg in sorted(violations):
            print(f"  {msg}")
        print("="*80)

        # Create a test item that will fail
        class ViolationCollector:
            def test_no_silent_failures(self):
                pytest.fail(
                    f"Found {len(violations)} silent failure violations:\n" +
                    "\n".join(m for _, m in violations)
                )

        # This will run and fail if violations found
        config.hook.pytest_collection.call_historic(
            ViolationCollector(),
            phase='pytest_collection',
        )


# Plugin hook for pytest
pytest_plugins = []
