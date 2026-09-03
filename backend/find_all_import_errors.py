#!/usr/bin/env python3
"""Find import errors by analyzing AST and comparing used vs imported names"""

import ast
import sys
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).parent

class ImportAnalyzer(ast.NodeVisitor):
    """Analyze imports and name usage in a Python file"""

    def __init__(self):
        self.imported_names = set()
        self.used_names = set()
        self.current_scope = {'builtins'}  # Built-in functions
        # Add common builtins
        self.current_scope.update(['print', 'len', 'str', 'int', 'dict', 'list', 'set', 'tuple', 'open', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round', 'isinstance', 'hasattr', 'getattr', 'setattr', 'delattr', 'callable', 'classmethod', 'staticmethod', 'property', 'super'])

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imported_names.add(name.split('.')[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == '*':
                # Wildcard import - assume all external names are imported
                return
            name = alias.asname if alias.asname else alias.name
            self.imported_names.add(name)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.used_names.add(node.id)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Add function name to scope
        self.imported_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # Add class name to scope
        self.imported_names.add(node.name)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        # Lambda params are local
        self.generic_visit(node)

    def get_undefined(self):
        """Return names that are used but not imported or defined"""
        undefined = self.used_names - self.imported_names - self.current_scope
        # Filter out common false positives
        undefined.discard('__name__')
        undefined.discard('__doc__')
        undefined.discard('__file__')
        undefined.discard('__all__')
        return sorted(undefined)


def analyze_file(filepath):
    """Analyze a single Python file for undefined names"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None  # Skip files with syntax errors

        analyzer = ImportAnalyzer()
        analyzer.visit(tree)
        undefined = analyzer.get_undefined()

        return undefined if undefined else None
    except Exception:
        return None


# Scan all Python files
print("🔍 Scanning for undefined names...\n")
errors_by_name = defaultdict(list)
total_files = 0
files_with_errors = 0

for pyfile in sorted(BACKEND_DIR.rglob("*.py")):
    if '__pycache__' in str(pyfile) or 'venv' in str(pyfile):
        continue

    total_files += 1
    undefined = analyze_file(pyfile)
    if undefined:
        files_with_errors += 1
        rel_path = pyfile.relative_to(BACKEND_DIR)
        for name in undefined:
            errors_by_name[name].append(str(rel_path))

# Print results
if errors_by_name:
    print(f"❌ {len(errors_by_name)} undefined names in {files_with_errors} files:\n")

    for name in sorted(errors_by_name.keys()):
        files = sorted(errors_by_name[name])
        print(f"'{name}': used in {len(files)} files")
        for filepath in files[:3]:
            print(f"  - {filepath}")
        if len(files) > 3:
            print(f"  ... + {len(files) - 3} more")
        print()
else:
    print(f"✅ No undefined names found in {total_files} files!")

print(f"\nSummary:")
print(f"  Files scanned: {total_files}")
print(f"  Files with errors: {files_with_errors}")
print(f"  Unique undefined names: {len(errors_by_name)}")
