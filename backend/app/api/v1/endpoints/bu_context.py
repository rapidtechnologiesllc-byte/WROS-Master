"""
Top-bar business unit selector (S-205/HRMS-0107, reworked CEO 2026-11-02: "the BU selection here is
wrong, it has to be rolled up from user login ... me as the CEO shouldnt have any restriction but
partner should only see their BU stuff & P&L").

Prefix: /bu-context

GET  /bu-context/my-access -- the BUs the user may look at, straight from their role template
                              (app.core.visibility.scope_bu_ids): org-level -> every active BU;
                              partner / BU head / member -> their BUs, with how they relate.
POST /bu-context/switch    -- checks a choice is inside that scope before the browser sends it.

The browser sends the choice as X-BU-View; app.core.bu_view keeps it for the request and
visibility.get_user_bu_ids narrows every screen to it. It can only narrow, never widen.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.schemas.bu_context import BUAccessItem, MyBUAccessResponse, SwitchBURequest

router = APIRouter(prefix="/bu-context", tags=["bu-context"])

def _scope(db: Session, user: Users):
    from app.core.visibility import scope_bu_ids
    return scope_bu_ids(db, user)


def _roles(db: Session, user: Users) -> dict:
    """bu_id -> how the user relates to it: Partner, BU Head (company), Member."""
    from app.models.business_unit import BusinessUnitLocationHead
    from app.models.location import Location

    roles: dict = {}
    for bu in db.query(BusinessUnit).filter(BusinessUnit.partner_user_id == user.UserID):
        roles.setdefault(bu.id, []).append("Partner")
    for bu_id, company in (db.query(BusinessUnitLocationHead.business_unit_id, Location.name)
                           .outerjoin(Location, Location.id == BusinessUnitLocationHead.company_id)
                           .filter(BusinessUnitLocationHead.head_user_id == user.UserID)):
        roles.setdefault(bu_id, []).append(f"BU Head ({company})" if company else "BU Head")
    if user.business_unit_id is not None and not roles.get(user.business_unit_id):
        roles.setdefault(user.business_unit_id, []).append("Member")
    return roles


@router.get(
    "/my-access",
    response_model=MyBUAccessResponse,
    dependencies=[Depends(require_resource_permission("dashboard", "view"))]
)
def my_bu_access(current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """The business units this user may look at, from their role template (app.core.visibility):
    org-level users every active BU (default view: all), partners the BUs they partner, BU heads
    the BUs they head, anyone else their own BU."""
    from app.core.bu_view import active_bu

    scope = _scope(db, current_user)
    query = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == current_user.tenant_id)
    query = query.filter(BusinessUnit.active.is_(True)) if scope is None else query.filter(BusinessUnit.id.in_(scope or {-1}))
    roles = {} if scope is None else _roles(db, current_user)
    items = [
        BUAccessItem(business_unit_id=bu.id, name=bu.display_name or bu.name,
                     continent=getattr(bu, "continent", None), region=getattr(bu, "region", None),
                     is_default=bu.id == current_user.business_unit_id, roles=roles.get(bu.id, []))
        for bu in query.order_by(BusinessUnit.name).all()
    ]
    chosen = active_bu()
    in_scope = chosen is not None and any(item.business_unit_id == chosen for item in items)
    return MyBUAccessResponse(access=items, can_view_all_bus=scope is None,
                              active_business_unit_id=chosen if in_scope else None)


@router.post(
    "/switch",
    dependencies=[Depends(require_resource_permission("dashboard", "view"))]
)
def switch_bu(body: SwitchBURequest, current_user: Users = Depends(get_current_internal_user), db: Session = Depends(get_db)):
    """Check a selector choice before the browser starts sending it: only a BU inside the user's
    scope (any active BU for org-level users)."""
    scope = _scope(db, current_user)
    unit = db.query(BusinessUnit).filter(BusinessUnit.id == body.business_unit_id,
                                         BusinessUnit.tenant_id == current_user.tenant_id).first()
    if unit is None or (scope is not None and unit.id not in scope):
        raise HTTPException(status_code=403, detail="That business unit is outside what you can see.")
    return {"active_business_unit_id": unit.id}
