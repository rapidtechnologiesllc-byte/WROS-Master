"""
Partner incentive eligibility/calculation, 2026-08-05. Avinash's direct
example: Troy earns a one-time $10K new-logo bonus per new AXION client,
triggered by MSA signed AND first revenue invoice -- "this is not
applicable to Curtis" (his incentive is a revenue-share on PRISM Core,
import logging
a structurally different mechanism, not just a different amount).

Deliberately data-driven, not hardcoded per-partner logic: eligibility
is "does an active PartnerIncentiveRule exist for this partner_user_id
+ incentive_type," never a name check. A future sales hire becomes
eligible by getting a rule row, never by a code change -- directly
per Avinash's own framing ("when we add more sales people in the
future we need to also check if they are eligible... and the amount
and mechanism").

MSA-signed proxy: Client.contract_start_date being set (this codebase
has no separate "MSA signed" flag; the contract fields already on
Client represent exactly this). First revenue invoice: the earliest
non-DRAFT Invoice for that client.
"""
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


INCENTIVE_TYPES = ("NEW_LOGO_BONUS", "REVENUE_SHARE", "DEPLOYMENT_BONUS", "OTHER")
INCENTIVE_EVENT_STATUSES = ("PENDING", "PAID")

logger = logging.getLogger(__name__)

class PartnerIncentiveRule(Base):
    """Config data, not code -- one row per partner per incentive type
    they're actually eligible for. No row = not eligible, structurally
    (this is how Curtis staying ineligible for NEW_LOGO_BONUS works --
    no special-case exclusion needed, there's simply no rule for him)."""
    __tablename__ = "partner_incentive_rules"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    partner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    incentive_type = Column(Enum(*INCENTIVE_TYPES, name="incentive_type", native_enum=False, create_constraint=True), nullable=False)

    # Flat one-time bonus (NEW_LOGO_BONUS, DEPLOYMENT_BONUS).
    amount_usd_cents = Column(Integer, nullable=True)
    # Ongoing revenue-share (REVENUE_SHARE) -- percentage, not a figure
    # pulled from the real finance workbook (that data stays out of
    # this repo per the standing rule); Avinash configures the real
    # number directly when he sets this rule up.
    revenue_share_pct = Column(Numeric(5, 2), nullable=True)

    trigger_description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

    partner = relationship("Users", foreign_keys=[partner_user_id])


class PartnerIncentiveEvent(Base):
    """One row per earned incentive -- idempotent per (rule, client) for
    NEW_LOGO_BONUS so re-running the eligibility check never double-pays."""
    __tablename__ = "partner_incentive_events"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    rule_id = Column(String(512), ForeignKey("partner_incentive_rules.id"), nullable=False, index=True)
    partner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=True, index=True)

    amount_usd_cents = Column(Integer, nullable=False)
    status = Column(Enum(*INCENTIVE_EVENT_STATUSES, name="incentive_event_status", native_enum=False, create_constraint=True), nullable=False, default="PENDING")
    triggered_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)

    # 2026-08-06, EPIC-16 Partner Incentive Calculator -- REVENUE_SHARE
    # events are period-based (once per rule per month), not per-client
    # like NEW_LOGO_BONUS, so client_id is always null for these. NULL
    # isn't unique-constrainable across SQL dialects the way (rule_id,
    # client_id) is for new-logo bonuses -- idempotency for revenue
    # share is an application-level check in
    # calculate_revenue_share_payout(), not a DB constraint.
    period_year = Column(Integer, nullable=True)
    period_month = Column(Integer, nullable=True)

    __table_args__ = (
        # DB-level idempotency -- see check_new_logo_incentive_service's
        # module docstring. An application-side "does this exist
        # already" check alone races under concurrent calls; this makes
        # a double-fire a constraint violation, not a duplicate row.
        UniqueConstraint('rule_id', 'client_id', name='uq_partner_incentive_events_rule_client'),
    )
