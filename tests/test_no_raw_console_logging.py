"""
HRMS-0117: "no raw console logging anywhere in the codebase, CI-enforced."

Parses every .py file under app/ with Python's ast module (not a text
grep, so commented-out print() calls and the word "print" inside a
string literal don't cause false positives) and fails if any live code
calls the builtin print(). Run this in CI so a future PR that
reintroduces a stray print() fails the build instead of waiting for
manual review to notice.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _find_print_calls(py_file: Path):
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            hits.append(node.lineno)
    return hits


def test_no_raw_print_calls_anywhere_under_app():
    offenders = {}
    for py_file in APP_DIR.rglob("*.py"):
        hits = _find_print_calls(py_file)
        if hits:
            offenders[str(py_file.relative_to(APP_DIR.parent))] = hits

    assert not offenders, (
        "Raw print() calls found outside the structured logger (HRMS-0117 requires "
        f"none, CI-enforced): {offenders}. Use app.core.logging's logger instead."
    )
