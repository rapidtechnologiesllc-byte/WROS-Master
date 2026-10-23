"""
Regression test for a critical bug found while building HRMS-0114's
audit tool: AuthenticationMiddleware._is_public_route() used to prefix-
match against the full PUBLIC_ROUTES list, which includes "/" -- and
every path starts with "/", so every route was being treated as public
(auth skipped) whenever this middleware ran. This proves the fix: only
explicit PREFIX_ROUTES entries (e.g. "/static") get prefix matching;
everything else in PUBLIC_ROUTES is exact-match only.

Note: this middleware is not currently registered in app.main (see the
developer handoff for why) -- this test protects the class's own logic
regardless of when it gets wired in.
"""
from app.middleware.auth_middleware import AuthenticationMiddleware


def _mw():
    return AuthenticationMiddleware(app=lambda scope, receive, send: None)


def test_exact_public_routes_are_public():
    mw = _mw()
    for path in ["/", "/health", "/docs", "/redoc", "/openapi.json", "/auth/v1/signup", "/auth/login"]:
        assert mw._is_public_route(path) is True


def test_static_subtree_is_public_via_explicit_prefix():
    mw = _mw()
    assert mw._is_public_route("/static/logo.png") is True
    assert mw._is_public_route("/docs/oauth2-redirect") is True


def test_negative_case_protected_routes_are_not_public():
    """
    The core regression check: before the fix, ALL of these would have
    incorrectly returned True because they start with "/".
    """
    mw = _mw()
    for path in ["/candidates", "/api/v1/candidates/123", "/reports", "/admin/users"]:
        assert mw._is_public_route(path) is False


def test_stale_paths_that_never_matched_any_real_route_are_gone():
    """
    /auth/v1/login and /auth/candidate/login used to be listed here but
    matched no real route (login is unified into a single POST
    /auth/login) -- meaning if this middleware were ever enabled, the
    actual login endpoint would have demanded a token to reach the
    endpoint that produces one. Guards against that drift recurring.
    """
    mw = _mw()
    assert "/auth/v1/login" not in mw.PUBLIC_ROUTES
    assert "/auth/candidate/login" not in mw.PUBLIC_ROUTES


def test_public_routes_matches_the_real_apps_actual_auth_paths():
    """
    Cross-checks PUBLIC_ROUTES against the routes app.main actually
    registers, so this list can't silently drift from reality again.
    """
    from app.core.route_security_audit import _iter_leaf_routes
    from app.main import app

    real_paths = {r.path for r in _iter_leaf_routes(app.routes)}
    assert "/auth/login" in real_paths
    assert "/auth/v1/signup" in real_paths
    assert "/auth/login" in AuthenticationMiddleware.PUBLIC_ROUTES
    assert "/auth/v1/signup" in AuthenticationMiddleware.PUBLIC_ROUTES


def test_templated_public_route_matches_a_real_resolved_path():
    """
    request.url.path is the RESOLVED path (e.g. "/jobs/abc123/apply"),
    never the literal "{job_id}" placeholder -- a plain string/prefix
    match against the template would never match a real request. This
    is the specific bug the segment matcher exists to avoid.
    """
    mw = _mw()
    assert mw._is_public_route("/jobs/abc123/apply") is True
    assert mw._is_public_route("/jobs/JOB-2026-0042/apply") is True


def test_templated_public_route_does_not_over_match():
    """
    "/jobs/{job_id}/apply" must not make the rest of /jobs/* public --
    only that exact shape, and only a single path segment for {job_id}.
    """
    mw = _mw()
    assert mw._is_public_route("/jobs/active-jobs") is False
    assert mw._is_public_route("/jobs/abc123") is False
    assert mw._is_public_route("/jobs/abc123/apply/extra") is False
    assert mw._is_public_route("/jobs/abc123/edit") is False
