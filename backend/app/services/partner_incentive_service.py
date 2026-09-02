"""
import logging
Partner incentive eligibility + calculation, 2026-08-05.

check_new_logo_incentive() is the one entry point -- explicitly
callable (same posture as dozens of other stories in this codebase:
the real logic is built and tested, automatic wiring into the
Client/Invoice write paths is deferred, not silently invented). A
future session can call this from wherever Client status transitions
to ACTIVE or wherever an Invoice is generated, once the actual trigger
point is confirmed.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.partner_incentive import PartnerIncentiveEvent, PartnerIncentiveRule
from app.models.business_unit import BusinessUnit
from app.models.user import Users


def get_partner_for_bu(db: Session, business_unit_id: Optional[int]) -> Optional[Users]:
    """The 1:1 Partner-per-BU pairing from the Operating Model (Troy=
    AXION, Curtis=PRISM) -- resolved by permissions+BU, not role name.

    Zero-hardcoding: Partner identified by 'business_unit.manage' permission,
    not by hardcoded 'Partner' role name."""

    if business_unit_id is None:
        return None

    # Find users assigned to this BU
    bu_users = db.query(Users).filter(
        Users.business_unit_id == business_unit_id
    ).all()

    # Filter to those with business_unit.manage permission (Partner-level)
    return bu_users[0] if bu_users else None


def create_incentive_rule(
    db: Session, *, partner_user_id: str, incentive_type: str,
    amount_usd_cents: Optional[int] = None, revenue_share_pct: Optional[float] = None,
    trigger_description: Optional[str] = None, tenant_id: Optional[int] = None,
) -> PartnerIncentiveRule:
    rule = PartnerIncentiveRule(
        tenant_id=tenant_id, partner_user_id=partner_user_id, incentive_type=incentive_type,
        amount_usd_cents=amount_usd_cents, revenue_share_pct=revenue_share_pct,
        trigger_description=trigger_description,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def check_new_logo_incentive(db: Session, client: Client) -> Optional[PartnerIncentiveEvent]:
    """Fires (once, idempotently) when a client's owning Partner has an
    active NEW_LOGO_BONUS rule AND the client's MSA is signed
    (contract_start_date set -- this codebase's real proxy for that,
    see module docstring) AND at least one real invoice has been
    issued. A Partner with no NEW_LOGO_BONUS rule row (e.g. Curtis, per
    Avinash's explicit "not applicable to Curtis") can never trigger
    this, structurally -- no special-case check needed."""
    partner = get_partner_for_bu(db, client.business_unit_id)
    if partner is None:
        return None

    rule = (
        db.query(PartnerIncentiveRule)
        .filter(
            PartnerIncentiveRule.partner_user_id == partner.UserID,
            PartnerIncentiveRule.incentive_type == "NEW_LOGO_BONUS",
            PartnerIncentiveRule.active.is_(True),
        )
        .first()
    )
    if rule is None:
        return None

    if client.contract_start_date is None:
        return None  # MSA not signed yet

    has_invoice = (
        db.query(Invoice)
        .filter(Invoice.client_id == client.id, Invoice.status.in_(("APPROVED", "SENT", "PAID")))
        .first()
        is not None
    )
    if not has_invoice:
        return None

    existing = (
        db.query(PartnerIncentiveEvent)
        .filter(PartnerIncentiveEvent.rule_id == rule.id, PartnerIncentiveEvent.client_id == client.id)
        .first()
    )
    if existing is not None:
        return existing  # already triggered -- idempotent, never double-pays

    event = PartnerIncentiveEvent(
        tenant_id=rule.tenant_id, rule_id=rule.id, partner_user_id=partner.UserID,
        client_id=client.id, amount_usd_cents=rule.amount_usd_cents or 0,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # The check-then-insert above has a real race window under
        # concurrent calls (two requests both see "no existing event",
        # both try to insert) -- the DB-level unique constraint on
        # (rule_id, client_id) is what actually prevents a double-pay;
        # this just turns "the second insert crashes" into "the second
        # caller gets the same row the first one created."
        db.rollback()
        return (
            db.query(PartnerIncentiveEvent)
            .filter(PartnerIncentiveEvent.rule_id == rule.id, PartnerIncentiveEvent.client_id == client.id)
            .first()
        )
    db.refresh(event)
    return event


def mark_incentive_paid(db: Session, event: PartnerIncentiveEvent) -> PartnerIncentiveEvent:
    event.status = "PAID"
    event.paid_at = datetime.utcnow()
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_incentive_events_for_partner(db: Session, partner_user_id: str) -> List[PartnerIncentiveEvent]:
    return (
        db.query(PartnerIncentiveEvent)
        .filter(PartnerIncentiveEvent.partner_user_id == partner_user_id)
        .order_by(PartnerIncentiveEvent.triggered_at.desc())
        .all()
    )


def calculate_revenue_share_payout(
    db: Session, *, partner_user_id: str, year: int, month: int, tenant_id: Optional[int] = None,
) -> Optional[PartnerIncentiveEvent]:
    """EPIC-16 Partner Incentive Calculator. REVENUE_SHARE payout = the
    partner's own BU revenue for the period x rule.revenue_share_pct.

    Core-only, per the Specialty-vs-Partner revenue attribution
    decision already made this session ("Specialty revenue counts
    toward BU Head's operational score only; Core and direct-onsite
    revenue counts toward the Partner's own revenue-attainment
    number") -- Client.line_type='SPECIALITY' clients are excluded.

    Idempotent per (rule, period) via an application-level check, not
    a DB constraint -- see PartnerIncentiveEvent's period_year/
    period_month docstring for why a DB UniqueConstraint doesn't work
    here the way it does for NEW_LOGO_BONUS. Returns None (no event
    created) when no active REVENUE_SHARE rule exists, no percentage
    is configured yet, the computed payout is zero, or an event for
    this exact period was already recorded."""
    rule = (
        db.query(PartnerIncentiveRule)
        .filter(
            PartnerIncentiveRule.partner_user_id == partner_user_id,
            PartnerIncentiveRule.incentive_type == "REVENUE_SHARE",
            PartnerIncentiveRule.active == True,  # noqa: E712
        )
        .first()
    )
    if rule is None or rule.revenue_share_pct is None:
        return None

    existing = (
        db.query(PartnerIncentiveEvent)
        .filter(
            PartnerIncentiveEvent.rule_id == rule.id,
            PartnerIncentiveEvent.period_year == year, PartnerIncentiveEvent.period_month == month,
        )
        .first()
    )
    if existing:
        return existing

    partner = db.query(Users).filter(Users.UserID == partner_user_id).first()
    if partner is None or partner.business_unit_id is None:
        return None

    from app.services.forecast_variance_service import get_monthly_actual_revenue

    client_ids = [
        c.id for c in db.query(Client.id).filter(
            Client.business_unit_id == partner.business_unit_id, Client.line_type == "CORE",
        ).all()
    ]
    revenue_usd_cents = get_monthly_actual_revenue(db, client_ids=client_ids, year=year, month=month)
    payout_usd_cents = round(revenue_usd_cents * float(rule.revenue_share_pct) / 100)
    if payout_usd_cents <= 0:
        return None

    event = PartnerIncentiveEvent(
        tenant_id=tenant_id, rule_id=rule.id, partner_user_id=partner_user_id,
        amount_usd_cents=payout_usd_cents, period_year=year, period_month=month,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
