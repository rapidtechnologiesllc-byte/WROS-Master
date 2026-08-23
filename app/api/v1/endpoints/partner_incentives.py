"""
Partner incentive rules + events, 2026-08-05.
Prefix: /partner-incentives

POST /partner-incentives/rules                    -- configure eligibility (revenue.view_pnl -- comp data)
GET  /partner-incentives/partners/{id}/events      -- a partner's own earned incentives
POST /partner-incentives/clients/{id}/check-new-logo -- explicit trigger check (not yet wired to any
                                                          automatic event -- see service module docstring)
POST /partner-incentives/events/{id}/mark-paid
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.client import Client
from app.models.partner_incentive import PartnerIncentiveEvent
from app.models.user import Users
from app.schemas.partner_incentive import (
    IncentiveEventItem, IncentiveEventListResponse, IncentiveRuleCreateRequest, IncentiveRuleItem,
    RevenueShareCalculationResponse,
)
from app.services.partner_incentive_service import (
    calculate_revenue_share_payout, check_new_logo_incentive, create_incentive_rule,
    list_incentive_events_for_partner, mark_incentive_paid,
)

router = APIRouter(prefix="/partner-incentives", tags=["partner-incentives"])


@router.post("/rules", response_model=IncentiveRuleItem, status_code=201)
def create_rule(
    body: IncentiveRuleCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    return create_incentive_rule(
        db, partner_user_id=body.partner_user_id, incentive_type=body.incentive_type,
        amount_usd_cents=body.amount_usd_cents, revenue_share_pct=body.revenue_share_pct,
        trigger_description=body.trigger_description, tenant_id=current_user.tenant_id,
    )


@router.get("/partners/{partner_user_id}/events", response_model=IncentiveEventListResponse)
def get_partner_events(
    partner_user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    return IncentiveEventListResponse(events=list_incentive_events_for_partner(db, partner_user_id))


@router.post("/clients/{client_id}/check-new-logo", response_model=IncentiveEventItem)
def check_new_logo(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    event = check_new_logo_incentive(db, client)
    if event is None:
        raise HTTPException(status_code=409, detail="Not yet eligible -- MSA not signed, no invoice, or no rule configured for this client's Partner.")
    return event


@router.post("/partners/{partner_user_id}/calculate-revenue-share", response_model=RevenueShareCalculationResponse)
def calculate_revenue_share(
    partner_user_id: str, year: int, month: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """EPIC-16 Partner Incentive Calculator. Idempotent per (partner,
    period) -- calling this twice for the same month never double-pays,
    see calculate_revenue_share_payout()'s own docstring."""
    existing_before = [
        e for e in list_incentive_events_for_partner(db, partner_user_id)
        if e.period_year == year and e.period_month == month
    ]
    event = calculate_revenue_share_payout(db, partner_user_id=partner_user_id, year=year, month=month, tenant_id=current_user.tenant_id)
    return RevenueShareCalculationResponse(event=event, already_calculated=bool(existing_before))


@router.post("/events/{event_id}/mark-paid", response_model=IncentiveEventItem)
def mark_paid(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    event = db.query(PartnerIncentiveEvent).filter(PartnerIncentiveEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Incentive event {event_id!r} not found.")
    return mark_incentive_paid(db, event)
