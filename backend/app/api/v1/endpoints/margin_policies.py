"""Rate card / margin floor (CEO 2026-10-23, gap 4) -- P&L > Rate Card tab.
=========================================================================
Prefix: /margin-policies
Tag:    margin-policies

Finance keeps one row per delivery engine (SPECIALITY = Staff Aug, CORE = direct client),
optionally per delivery country and role: min_margin_pct (below it a BU Head approves the
placement) and hard_floor_pct (below it a Partner approves). The allocation create / edit paths
read it through app.services.margin_guard_service. Nothing is seeded: no row = no floor (allowed
and flagged). Permission: the finance-operations resource, like the cost rates beside it.

Routes:
  GET    /margin-policies          Every row of the caller's tenant, plus the engines and countries.
  POST   /margin-policies          Add a row.
  PUT    /margin-policies/{id}     Change a row (percentages, active).
  DELETE /margin-policies/{id}     Remove a row.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.employee import DELIVERY_ENGINES
from app.models.margin_policy import MarginPolicy
from app.models.user import Users

router = APIRouter(prefix="/margin-policies", tags=["margin-policies"])


class MarginPolicyRequest(BaseModel):
    delivery_engine: str
    country: Optional[str] = None
    role: Optional[str] = None
    min_margin_pct: float
    hard_floor_pct: float
    active: bool = True


class MarginPolicyItem(BaseModel):
    id: int
    delivery_engine: str
    country: Optional[str] = None
    role: Optional[str] = None
    min_margin_pct: float
    hard_floor_pct: float
    active: bool


class MarginPolicyListResponse(BaseModel):
    policies: List[MarginPolicyItem]
    engines: List[dict]
    countries: List[dict]


def _item(row: MarginPolicy) -> MarginPolicyItem:
    return MarginPolicyItem(id=row.id, delivery_engine=row.delivery_engine, country=row.country, role=row.role,
                            min_margin_pct=float(row.min_margin_pct), hard_floor_pct=float(row.hard_floor_pct),
                            active=bool(row.active))


def _countries() -> List[dict]:
    from app.services import employment_type_policy

    return [{"code": c["code"], "name": c["name"]} for c in employment_type_policy.describe()["countries"]]


def _validated(db: Session, body: MarginPolicyRequest, tenant_id: int, exclude_id: Optional[int] = None) -> dict:
    if body.delivery_engine not in DELIVERY_ENGINES:
        raise HTTPException(status_code=422, detail=f"Delivery engine must be one of {list(DELIVERY_ENGINES)}.")
    country = (body.country or "").strip().upper() or None
    if country is not None and country not in {c["code"] for c in _countries()}:
        raise HTTPException(status_code=422, detail=f"Unknown country {country!r}: use a configured country code.")
    role = (body.role or "").strip() or None
    if not (-100 <= body.hard_floor_pct <= body.min_margin_pct < 100):
        raise HTTPException(status_code=422, detail="Percentages must satisfy -100 <= hard floor <= minimum < 100.")
    clash = db.query(MarginPolicy.id).filter(
        MarginPolicy.tenant_id == tenant_id, MarginPolicy.delivery_engine == body.delivery_engine,
        func.coalesce(MarginPolicy.country, "") == (country or ""),
        func.lower(func.coalesce(MarginPolicy.role, "")) == (role or "").lower())
    if exclude_id is not None:
        clash = clash.filter(MarginPolicy.id != exclude_id)
    if clash.first() is not None:
        raise HTTPException(status_code=409, detail="A row for this engine, country and role already exists; edit it.")
    return {"delivery_engine": body.delivery_engine, "country": country, "role": role,
            "min_margin_pct": body.min_margin_pct, "hard_floor_pct": body.hard_floor_pct, "active": body.active}


@router.get(
    "",
    response_model=MarginPolicyListResponse,
    summary="The rate card: margin floors by delivery engine, country and role",
    dependencies=[Depends(require_resource_permission("finance-operations", "view"))],
)
def list_margin_policies(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.deployment_readiness_service import DELIVERY_LINE_LABELS

    rows = (db.query(MarginPolicy).filter(MarginPolicy.tenant_id == current_user.tenant_id)
            .order_by(MarginPolicy.delivery_engine, MarginPolicy.country, MarginPolicy.role).all())
    return MarginPolicyListResponse(
        policies=[_item(r) for r in rows],
        engines=[{"code": e, "name": DELIVERY_LINE_LABELS.get(e, e)} for e in DELIVERY_ENGINES],
        countries=_countries(),
    )


@router.post(
    "",
    response_model=MarginPolicyItem,
    summary="Add a margin floor row",
    dependencies=[Depends(require_resource_permission("finance-operations", "create"))],
)
def create_margin_policy(
    body: MarginPolicyRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    row = MarginPolicy(tenant_id=current_user.tenant_id, created_by=current_user.UserID,
                       updated_by=current_user.UserID, **_validated(db, body, current_user.tenant_id))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item(row)


def _row_or_404(db: Session, policy_id: int, user: Users) -> MarginPolicy:
    row = db.query(MarginPolicy).filter(MarginPolicy.id == policy_id, MarginPolicy.tenant_id == user.tenant_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Margin floor row not found.")
    return row


@router.put(
    "/{policy_id}",
    response_model=MarginPolicyItem,
    summary="Change a margin floor row",
    dependencies=[Depends(require_resource_permission("finance-operations", "edit"))],
)
def update_margin_policy(
    policy_id: int,
    body: MarginPolicyRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    row = _row_or_404(db, policy_id, current_user)
    for key, value in _validated(db, body, current_user.tenant_id, exclude_id=row.id).items():
        setattr(row, key, value)
    row.updated_by = current_user.UserID
    db.commit()
    db.refresh(row)
    return _item(row)


@router.delete(
    "/{policy_id}",
    summary="Remove a margin floor row",
    dependencies=[Depends(require_resource_permission("finance-operations", "delete"))],
)
def delete_margin_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    row = _row_or_404(db, policy_id, current_user)
    db.delete(row)
    db.commit()
    return {"deleted": policy_id}
