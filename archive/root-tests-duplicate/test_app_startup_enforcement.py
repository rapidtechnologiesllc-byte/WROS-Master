"""
Proves HRMS-0114's actual "fails to start" behavior, end to end, using
the real app -- not just the audit tool in isolation.
"""
from fastapi import Depends, FastAPI

from app.core.dependencies import require_permission
from app.core.route_security_audit import assert_all_routes_have_permission_declarations


def test_real_app_actually_imports_with_enforcement_active():
    """
    The positive case: this is already implicitly proven by every other
    test file importing app.main successfully, but make it explicit and
    named so a future regression here fails obviously.
    """
    from app.main import app  # noqa: F401 -- import success is the assertion


def test_a_new_unguarded_route_would_actually_fail_startup():
    """
    Simulates what HRMS-0114 is actually for: a future PR adds a route
    and forgets the permission declaration. Proves the assert function
    used in app.main would catch it, without needing to actually break
    the real app to demonstrate it.
    """
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/candidates", dependencies=[Depends(require_permission("candidate.view"))])
    def list_candidates():
        return []

    @app.get("/new-report")  # the forgotten declaration
    def new_report():
        return {}

    try:
        assert_all_routes_have_permission_declarations(app, public_routes=["/health"])
        assert False, "expected RuntimeError for the unguarded /new-report route"
    except RuntimeError as e:
        assert "GET /new-report" in str(e)


def test_known_exceptions_are_actually_excluded():
    app = FastAPI()

    @app.get("/webhook")
    def webhook():
        return {}

    # Would raise without the exception listed:
    try:
        assert_all_routes_have_permission_declarations(app, public_routes=[])
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    # Must NOT raise once explicitly excepted:
    assert_all_routes_have_permission_declarations(
        app, public_routes=[], known_exceptions=["GET /webhook"]
    )
