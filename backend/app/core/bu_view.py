"""The business unit a user is looking at (the BU selector in the top bar, CEO 2026-11-02: "me as
the CEO shouldnt have any restriction but partner should only see their BU stuff & P&L").

What a user MAY see is decided by their role template (app.core.visibility.scope_bu_ids). The
selector only NARROWS that to one business unit for the screens they open: the browser sends the
choice as X-Active-BU-Id on every request, this middleware keeps it for the request, and
visibility.get_user_bu_ids intersects it with the user's scope. A BU outside the scope is ignored,
never a way to see more.
"""
from contextvars import ContextVar
from typing import Optional

ACTIVE_BU_HEADER = b"x-active-bu-id"

_active_bu: ContextVar[Optional[int]] = ContextVar("active_bu", default=None)


def active_bu() -> Optional[int]:
    """The business unit chosen in the selector for this request, if any."""
    return _active_bu.get()


class ActiveBUMiddleware:
    """Pure ASGI, so the value is set in the request's own context before any handler runs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = dict(scope.get("headers") or []).get(ACTIVE_BU_HEADER, b"").decode().strip()
        token = _active_bu.set(int(raw) if raw.isdigit() else None)
        try:
            await self.app(scope, receive, send)
        finally:
            _active_bu.reset(token)
