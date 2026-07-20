"""
HRMS-0114 -- "every route has an explicit permission declaration or the
application fails to start."

This module provides the MECHANISM (find_routes_missing_permission_declaration
/ assert_all_routes_have_permission_declarations). It is deliberately NOT
wired into app.main's startup event yet: this codebase has existing
routes that predate RBAC and don't carry a require_permission()/
require_attribute() declaration. Flipping the hard-fail-at-startup switch
on before those are reviewed and fixed would crash the app in production
rather than catch a future regression, which is the opposite of the
intent.

Path to actually enabling it:
1. Run assert_all_routes_have_permission_declarations(app, PUBLIC_ROUTES)
   (or the reporting test in tests/test_route_permission_audit.py) to get
   the current list of non-compliant routes.
2. Add an explicit require_permission(...) or require_attribute(...)
   dependency to each one (or add it to PUBLIC_ROUTES if it's genuinely
   meant to be public).
3. Once the list is empty, call assert_all_routes_have_permission_declarations
   from app.main's startup_event so a future route that forgets its
   declaration fails startup immediately, per HRMS-0114.
"""
from typing import Iterable, List

from fastapi import FastAPI
from fastapi.routing import APIRoute

_MARKER_ATTRS = ("__wros_permission__", "__wros_attribute__")


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


def _route_has_permission_declaration(route: APIRoute) -> bool:
    dependant = route.dependant
    stack = [dependant]
    seen = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        call = getattr(current, "call", None)
        if call is not None and any(hasattr(call, attr) for attr in _MARKER_ATTRS):
            return True
        stack.extend(getattr(current, "dependencies", []) or [])
    return False


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


def find_routes_missing_permission_declaration(app: FastAPI, public_routes: Iterable[str]) -> List[str]:
    """Returns a sorted list of "METHOD path" strings for every non-public
    route that has no require_permission()/require_attribute() dependency
    anywhere in its dependency tree."""
    missing = []
    for route in _iter_leaf_routes(app.routes):
        if _is_public(route.path, public_routes):
            continue
        if not _route_has_permission_declaration(route):
            for method in sorted(route.methods or []):
                if method == "HEAD":
                    continue
                missing.append(f"{method} {route.path}")
    return sorted(set(missing))


def assert_all_routes_have_permission_declarations(app: FastAPI, public_routes: Iterable[str]) -> None:
    missing = find_routes_missing_permission_declaration(app, public_routes)
    if missing:
        raise RuntimeError(
            "HRMS-0114: the following routes have no permission declaration "
            f"(require_permission()/require_attribute()) and are not listed as "
            f"public: {missing}"
        )
