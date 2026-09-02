"""
Unit-tests the HRMS-0114 audit mechanism itself, on a small throwaway
FastAPI app (not the real one) -- proves the tool correctly tells apart
a public route, a properly-declared route, and a route with no
declaration at all.
"""
import pytest
import logging
from fastapi import Depends, FastAPI

from app.core.dependencies import require_permission, require_attribute
from app.core.route_security_audit import (
    find_routes_missing_permission_declaration,
    assert_all_routes_have_permission_declarations,
)

PUBLIC_ROUTES = ["/", "/docs", "/health"]


def _toy_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/candidates", dependencies=[Depends(require_permission("candidate.view"))])
    def list_candidates():
        return []

    @app.post("/candidates", dependencies=[Depends(require_attribute("pipeline_control"))])
    def create_candidate():
        return {}

    @app.get("/reports")  # <-- deliberately missing any permission declaration
    def reports():
        return {}

    return app


def test_public_and_declared_routes_are_not_flagged():
    app = _toy_app()
    missing = find_routes_missing_permission_declaration(app, PUBLIC_ROUTES)
    assert "GET /health" not in missing
    assert "GET /candidates" not in missing
    assert "POST /candidates" not in missing


def test_route_with_no_declaration_is_flagged():
    app = _toy_app()
    missing = find_routes_missing_permission_declaration(app, PUBLIC_ROUTES)
    assert "GET /reports" in missing


def test_assert_raises_when_any_route_is_missing_a_declaration():
    app = _toy_app()
    with pytest.raises(RuntimeError, match="GET /reports"):
        assert_all_routes_have_permission_declarations(app, PUBLIC_ROUTES)


def test_assert_passes_once_the_gap_is_fixed():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/reports", dependencies=[Depends(require_permission("reports.view"))])
    def reports():
        return {}

    assert_all_routes_have_permission_declarations(app, PUBLIC_ROUTES)  # must not raise
