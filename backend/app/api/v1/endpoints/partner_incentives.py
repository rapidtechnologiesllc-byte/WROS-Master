"""
Partner incentive rules + events, 2026-08-05.
Prefix: /partner-incentives

POST /partner-incentives/rules                                   -- configure eligibility (org-level only)
GET  /partner-incentives/partners/{id}/events                     -- a partner's own earned incentives
POST /partner-incentives/partners/{id}/calculate-revenue-share    -- monthly payout (org-level only)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import authority
from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.user import Users
from app.schemas.partner_incentive import (
    IncentiveEventListResponse, IncentiveRuleCreateRequest, IncentiveRuleItem,
    RevenueShareCalculationResponse,
)
from app.services.partner_incentive_service import (
    calculate_revenue_share_payout, create_incentive_rule, list_incentive_events_for_partner,
)

router = APIRouter(prefix="/partner-incentives", tags=["partner-incentives"])


def _ensure_org_level(db: Session, user: Users) -> None:
    """Incentive rules and payouts are the firm's decision, never the partner's own: only an
    org-level role template may set or calculate them (app.core.authority)."""
    if not authority.is_org_level(db, user):
        raise HTTPException(status_code=403, detail="Only org-level roles can set or calculate partner incentives.")


def _ensure_self_or_org(db: Session, user: Users, partner_user_id: str) -> None:
    """A partner sees their own incentives; another partner's are not found (no probing)."""
    if partner_user_id != user.UserID and not authority.is_org_level(db, user):
        raise HTTPException(status_code=404, detail="Partner not found")


@router.post(
    "/rules",
    response_model=IncentiveRuleItem,
    status_code=201,
    dependencies=[Depends(require_resource_permission("partner-dashboard", "create"))]
)
def create_rule(
    body: IncentiveRuleCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    _ensure_org_level(db, current_user)
    return create_incentive_rule(
        db, partner_user_id=body.partner_user_id, incentive_type=body.incentive_type,
        amount_usd_cents=body.amount_usd_cents, revenue_share_pct=body.revenue_share_pct,
        trigger_description=body.trigger_description, tenant_id=current_user.tenant_id,
    )

@router.get(
    "/partners/{partner_user_id}/events",
    response_model=IncentiveEventListResponse,
    dependencies=[Depends(require_resource_permission("partner-dashboard", "view"))]
)
def get_partner_events(
    partner_user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    _ensure_self_or_org(db, current_user, partner_user_id)
    return IncentiveEventListResponse(events=list_incentive_events_for_partner(db, partner_user_id))


@router.post(
    "/partners/{partner_user_id}/calculate-revenue-share",
    response_model=RevenueShareCalculationResponse,
    dependencies=[Depends(require_resource_permission("partner-dashboard", "create"))]
)
def calculate_revenue_share(
    partner_user_id: str, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """EPIC-16 Partner Incentive Calculator. Idempotent per (partner,
    period) -- calling this twice for the same month never double-pays,
    see calculate_revenue_share_payout()'s own docstring."""
    _ensure_org_level(db, current_user)
    existing_before = [
        e for e in list_incentive_events_for_partner(db, partner_user_id)
        if e.period_year == year and e.period_month == month
    ]
    event = calculate_revenue_share_payout(db, partner_user_id=partner_user_id, year=year, month=month, tenant_id=current_user.tenant_id)
    return RevenueShareCalculationResponse(event=event, already_calculated=bool(existing_before))

