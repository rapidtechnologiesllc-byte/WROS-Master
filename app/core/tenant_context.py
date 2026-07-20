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
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core.dependencies import get_current_internal_user
from app.models.user import Users


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
