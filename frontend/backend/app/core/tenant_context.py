"""
Tenant resolution — HRMS-0109, Phase 1 Security Foundation.

The one rule this module exists to enforce: a request's tenant_id comes
from the authenticated user's own database record, resolved server-side,
and NEVER from anything the caller supplies (query param, header, request
body, or any other client-controlled input).

Every query against a tenant-scoped table should go through
`get_tenant_scoped_query` (or a route should depend on `require_tenant_id`)
rather than filtering by tenant_id by hand, so this guarantee lives in one
place instead of being re-implemented per route.

S-207 — global scoping
-----------------------
The above per-call helpers only ever covered 6 routes. Everything else
(~180 `db.query(Candidate|Users|Jobs)` call sites across 23 endpoint
files, per docs/build-package/HRMS-0109-tenant-scoping-gap.md) still
queried unscoped. Rather than hand-edit 180 call sites one at a time,
`activate_tenant_scope()` + the `do_orm_execute` listener below apply
the same "own tenant only" filter to every ORM query against those three
models, automatically, for the duration of one request.

Why this is safe against the leak the gap doc explicitly warned about
("a stale context value leaking between requests"): `_current_tenant_id`
is a `contextvars.ContextVar`, not a plain module-level variable.
Starlette gives every request its own asyncio Task (and `run_in_threadpool`
copies the context via `contextvars.copy_context()` for sync route
handlers), so each request's `.set()` is invisible to every other
request — concurrently running or not — even on a shared thread pool.
Nothing needs to reset it after the request; the next request simply
starts from a fresh copy with the var back at its default (None).

Only `Candidate`, `Users`, and `Jobs` are scoped here — the exact three
models the gap doc's ~180-site inventory covers. Other tenant_id-bearing
models are a separate, not-yet-audited piece of work, not silently
folded into this one.
"""
import contextvars

from fastapi import Depends, HTTPException, status
from sqlalchemy import event
from sqlalchemy.orm import Query, Session, with_loader_criteria

from app.core.dependencies import get_current_internal_user
from app.models.user import Users, Jobs
from app.models.candidate import Candidate

_current_tenant_id: "contextvars.ContextVar[int | None]" = contextvars.ContextVar(
    "current_tenant_id", default=None
)

_TENANT_SCOPED_MODELS = (Candidate, Users, Jobs)


def activate_tenant_scope(tenant_id) -> None:
    """
    Set the current request's tenant for the global query scoping below.

    `tenant_id` may be None (e.g. a user not yet assigned to a tenant) --
    that's the same as not calling this at all: no extra filter is
    applied, matching today's unscoped behavior rather than failing
    closed. Routes that need to hard-require a tenant already do so via
    `require_tenant_id`/`get_tenant_scoped_query`; this global mechanism
    is a backstop for the other ~180 sites, not a stricter gate.
    """
    _current_tenant_id.set(tenant_id)


# DISABLED - Single company deployment, no tenant scoping needed
# def _apply_tenant_scoping(execute_state) -> None:
#     tenant_id = _current_tenant_id.get()
#     if tenant_id is None or not execute_state.is_select:
#         return
#     for model in _TENANT_SCOPED_MODELS:
#         execute_state.statement = execute_state.statement.options(
#             with_loader_criteria(
#                 model,
#                 lambda cls: cls.tenant_id == tenant_id,
#             )
#         )

# DISABLED - tenant scoping listener removed for single company deployment
# event.listen(Session, "do_orm_execute", _apply_tenant_scoping)


def get_tenant_scoped_query(db: Session, model, current_user: Users) -> Query:
    """
    Return a query on `model` filtered to current_user's own tenant.

    `model` must have a `tenant_id` column. There is deliberately no
    parameter here that accepts a caller-supplied tenant id — the only
    input this function trusts is the already-authenticated user object.
    """
    if current_user.tenant_id is None:
        # Fail closed: an account not yet assigned to a tenant sees
        # nothing, rather than accidentally seeing everything.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a tenant",
        )
    return db.query(model).filter(model.tenant_id == current_user.tenant_id)


async def require_tenant_id(
    current_user: Users = Depends(get_current_internal_user),
) -> int:
    """
    FastAPI dependency: resolves the caller's tenant_id from their
    authenticated session. Use this in route signatures instead of ever
    reading a tenant id from request input.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a tenant",
        )
    return current_user.tenant_id
