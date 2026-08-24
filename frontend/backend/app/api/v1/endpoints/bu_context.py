"""
S-205/HRMS-0107 -- Business Unit Entity & Context Switching.
==================================================================
Prefix: /bu-context
Tag:    bu-context

GET  /bu-context/my-access   -- BUs this user can access (>1 = real
                                 switcher; 1 = static label, per AC-1/BR-0107-03)
POST /bu-context/switch      -- validates membership before "switching"
                                 (this codebase has no server-side session
                                 store -- the frontend persists the choice
                                 and sends it back via X-Active-BU-Id on
                                 every request; get_active_business_unit_id()
                                 below re-validates it every single call,
                                 per BR-0107-01 -- never trusted from
                                 client state alone)
POST /bu-context/all-bus     -- Director/Super-User-only unscoped view,
                                 real audit_log entry per activation (BR-0107-02/AC-4)

get_active_business_unit_id() is the real integration point future BU-
scoped endpoints should adopt (Step 5 of the spec) -- not retrofitted
into every existing endpoint this pass, same honest-scope posture as
the tenant-scoping sweep this session already flagged as separate,
larger follow-up work.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.schemas.bu_context import BUAccessItem, MyBUAccessResponse, SwitchBURequest
from app.services.bu_context_service import (
    NotAuthorizedForAllBUs, NotYourBusinessUnit, activate_all_bus_view,
    ensure_default_bu_access, get_user_bu_access, switch_active_bu, validate_active_bu,
)

router = APIRouter(prefix="/bu-context", tags=["bu-context"])


def _user_can_view_all_bus(db: Session, current_user: Users) -> bool:
    """Check if user has permission to view all business units (not scoped to their BU)."""
    from app.services.permission_helper import PermissionHelper
    return PermissionHelper.has_any_permission(
        current_user.UserID,
        ["admin.manage", "business-units", "edit"],
        db,
        current_user.tenant_id
    )


async def get_active_business_unit_id(
    x_active_bu_id: Optional[int] = Header(None),
    current_user: Users = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> Optional[int]:
    """Reusable dependency for any BU-scoped endpoint (Step 5's real
    integration point). Re-validates the client-supplied header
    against the user's real bu_access rows on every call (BR-0107-01)
    -- a tampered/stale header is rejected with 403 (AC-3), never
    silently trusted or silently ignored."""
    if x_active_bu_id is None:
        return None
    try:
        validate_active_bu(db, current_user.UserID, x_active_bu_id)
    except NotYourBusinessUnit as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return x_active_bu_id


@router.get("/my-access", response_model=MyBUAccessResponse)
def my_bu_access(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    ensure_default_bu_access(db, current_user)  # idempotent -- backfills users who predate this story
    rows = get_user_bu_access(db, current_user.UserID)
    bu_ids = [r.business_unit_id for r in rows]
    bus_by_id = {b.id: b for b in db.query(BusinessUnit).filter(BusinessUnit.id.in_(bu_ids)).all()} if bu_ids else {}

    return MyBUAccessResponse(
        access=[
            BUAccessItem(
                business_unit_id=r.business_unit_id,
                name=bus_by_id[r.business_unit_id].name if r.business_unit_id in bus_by_id else "(unknown BU)",
                continent=bus_by_id[r.business_unit_id].continent if r.business_unit_id in bus_by_id else None,
                region=bus_by_id[r.business_unit_id].region if r.business_unit_id in bus_by_id else None,
                is_default=r.is_default,
            )
            for r in rows
        ],
        can_view_all_bus=_user_can_view_all_bus(db, current_user),
    )


@router.post("/switch")
def switch_bu(body: SwitchBURequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    try:
        switch_active_bu(db, current_user, body.business_unit_id)
    except NotYourBusinessUnit as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"active_business_unit_id": body.business_unit_id}


@router.post("/all-bus")
def all_bus_view(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    try:
        entry = activate_all_bus_view(db, current_user)
    except NotAuthorizedForAllBUs as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"activated": True, "audit_log_id": entry.id}
