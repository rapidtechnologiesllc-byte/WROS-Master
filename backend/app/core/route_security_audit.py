"""
HRMS-0114 -- "every route has an explicit permission declaration or the
import logging
application fails to start."

This module provides the mechanism
(find_routes_missing_permission_declaration /
assert_all_routes_have_permission_declarations), and as of 2026-07-20
IS wired into app.main's startup event -- the real-app audit reached 0
unexplained zero-identity-check routes (see
docs/build-package/HRMS-0114-route-gap.md for the full history of how
it got there), so a future route shipping with no auth at all now
fails the app at startup instead of silently going live.

find_routes_with_only_coarse_auth() is a SEPARATE, non-blocking list --
routes with a real but coarse identity check (any-logged-in-candidate
or any-logged-in-staff-member) rather than a specific
require_permission(). That list does not need to be empty for the
startup gate to be safely enabled; it's a lower-urgency tightening
effort tracked in tests/test_route_permission_audit_real_app.py.
"""
from typing import Iterable, List

from fastapi import FastAPI
from fastapi.routing import APIRoute

_RBAC_MARKER_ATTRS = ("__wros_permission__", "__wros_attribute__")
_COARSE_AUTHN_MARKER_ATTRS = ("__wros_authn__",)
_ALL_MARKER_ATTRS = _RBAC_MARKER_ATTRS + _COARSE_AUTHN_MARKER_ATTRS


def _is_public(path: str, public_routes: Iterable[str]) -> bool:
    """
    Exact match only. Deliberately NOT a prefix match against the full
    list -- "/" is a valid entry in public_routes and every path starts
    with "/", so a naive startswith() here would treat every route as
    public (see the identical bug fixed in AuthenticationMiddleware).
    Callers that need subtree matching (e.g. "/static/*") should list
    that subtree's exact known paths, or extend this function
    deliberately the same way PREFIX_ROUTES does in auth_middleware.py.
    """
    return path in public_routes


def _route_marker_attrs_present(route: APIRoute) -> set:
    """Returns the set of marker attribute names found anywhere in this
    route's dependency tree (e.g. {"__wros_permission__"})."""
    dependant = route.dependant
    stack = [dependant]
    seen = set()
    found = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        call = getattr(current, "call", None)
        if call is not None:
            for attr in _ALL_MARKER_ATTRS:
                if hasattr(call, attr):
                    found.add(attr)
        stack.extend(getattr(current, "dependencies", []) or [])
    return found


def _iter_leaf_routes(routes) -> Iterable[APIRoute]:
    """
    Recursively flattens whatever app.routes / router.routes actually
    contains down to leaf APIRoute objects. Newer FastAPI versions wrap
    each include_router() call in an internal _IncludedRouter rather
    than eagerly flattening into APIRoute objects at include-time, and
    nested include_router() calls (as this codebase does: app includes
    one top-level router, which itself includes ~20 per-feature
    routers) nest that wrapping multiple levels deep. Walk generically
    via .original_router.routes / .routes so this doesn't silently stop
    working on the next FastAPI version's internal structure.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router") and hasattr(route.original_router, "routes"):
            yield from _iter_leaf_routes(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from _iter_leaf_routes(route.routes)


def _non_public_routes_by_methods(app: FastAPI, public_routes: Iterable[str]):
    for route in _iter_leaf_routes(app.routes):
        if _is_public(route.path, public_routes):
            continue
        for method in sorted(route.methods or []):
            if method == "HEAD":
                continue
            yield f"{method} {route.path}", route


def find_routes_missing_permission_declaration(app: FastAPI, public_routes: Iterable[str]) -> List[str]:
    """
    Returns a sorted list of "METHOD path" strings for every non-public
    route with NO explicit identity/permission declaration at all --
    the genuinely dangerous category HRMS-0114 exists to catch. This
    counts require_permission()/require_attribute() (fine-grained RBAC)
    AND get_current_candidate()/get_current_hr_or_admin()/
    get_current_internal_user() (coarse but real identity checks) as
    satisfying the requirement -- see find_routes_with_only_coarse_auth()
    for the separate, lower-urgency list of routes that only have the
    coarse check and could be tightened to a specific permission later.
    """
    missing = []
    for label, route in _non_public_routes_by_methods(app, public_routes):
        if not _route_marker_attrs_present(route):
            missing.append(label)
    return sorted(set(missing))


def find_routes_with_only_coarse_auth(app: FastAPI, public_routes: Iterable[str]) -> List[str]:
    """
    Routes that have SOME identity check (candidate-self-service, or
    any-authenticated-internal-user) but no fine-grained RBAC
    permission. Not a startup-blocking gap -- these are legitimately
    protected today -- but worth tightening to a specific
    require_permission() as this codebase's RBAC coverage matures.
    """
    coarse = []
    for label, route in _non_public_routes_by_methods(app, public_routes):
        markers = _route_marker_attrs_present(route)
        if markers and not (markers & set(_RBAC_MARKER_ATTRS)):
            coarse.append(label)
    return sorted(set(coarse))


def assert_all_routes_have_permission_declarations(
    app: FastAPI,
    public_routes: Iterable[str],
    known_exceptions: Iterable[str] = (),
) -> None:
    """
    `known_exceptions` is for routes manually verified to have real
    protection this scanner structurally can't see (e.g. an in-function-
    body cookie check rather than a FastAPI Depends()) -- see
    app.main's call site for the current list and why each is there.
    Every exception here should have its own regression test guarding
    that the underlying protection hasn't quietly been removed.
    """
    missing = set(find_routes_missing_permission_declaration(app, public_routes)) - set(known_exceptions)
    if missing:
        raise RuntimeError(
            "HRMS-0114: the following routes have no explicit identity/permission "
            f"declaration at all and are not listed as public or a known exception: {sorted(missing)}"
        )
