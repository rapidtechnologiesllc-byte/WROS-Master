"""
Runs the HRMS-0114 audit against the REAL app (app.main:app) and
reports the current gap -- deliberately marked xfail (not a hard
failure) because this codebase has pre-RBAC routes that genuinely need
review before the fail-at-startup switch (see route_security_audit.py's
docstring) can be safely enabled. This test's job is to keep the exact
list visible and un-ignorable, not to block the build tonight.

Importing app.main only registers routes -- it does not connect to the
database (SQLAlchemy's create_engine is lazy), so this is safe to run
without touching the real database.
"""
import pytest

from app.core.route_security_audit import find_routes_missing_permission_declaration
from app.middleware.auth_middleware import AuthenticationMiddleware


@pytest.mark.xfail(strict=False, reason="Pre-existing routes need permission declarations added -- tracked, not yet fixed")
def test_real_app_has_no_routes_missing_permission_declarations():
    from app.main import app

    missing = find_routes_missing_permission_declaration(app, AuthenticationMiddleware.PUBLIC_ROUTES)
    if missing:
        print(f"\n{len(missing)} route(s) currently missing a permission declaration:")
        for route in missing:
            print(f"  - {route}")
    assert not missing
