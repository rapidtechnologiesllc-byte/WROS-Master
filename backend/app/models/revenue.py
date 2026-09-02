"""
import logging
Revenue Recognition & P&L Attribution Model.

Tracks revenue flows through the system:
- Invoice → Revenue Recognition (when PAID)
- Revenue attribution by Client Owner + Opportunity
- Partner revenue share calculation (Core business only)

Revenue is recognized (recorded) when Invoice.status = PAID, not when SENT.
All revenue flows to Client Owner (opportunity owner at time of creation).
Partner revenue share applies to Core business type only.
"""
import uuid

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer,
    String, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES

def _new_uuid() -> str:
    return str(uuid.uuid4())


REVENUE_SOURCES = ("INVOICE", "MANUAL_ADJUSTMENT", "CORRECTION")
BUSINESS_TYPES = ("CORE", "SPECIALITY")

logger = logging.getLogger(__name__)

class Revenue(Base):
    __tablename__ = "revenues"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    invoice_id = Column(String(512), ForeignKey("invoices.id"), nullable=False, index=True)
    opportunity_id = Column(String(512), ForeignKey("opportunities.id"), nullable=False, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)

    # P&L Attribution: all revenue flows to Client Owner (opportunity owner at time of creation)
    client_owner_id = Column(String(512), ForeignKey("users.UserID"), nullable=True, index=True)

    # Revenue amount in USD cents (from invoice)
    revenue_usd_cents = Column(Integer, nullable=False)
    currency = Column(
        Enum(*BILLING_CURRENCIES, name="revenue_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD",
    )

    # Business classification
    service = Column(String(512), nullable=True)  # From opportunity
    module = Column(String(512), nullable=True)   # From opportunity
    client_type = Column(String(512), nullable=True)  # From opportunity
    pricing_model = Column(String(512), nullable=True)  # From opportunity
    business_type = Column(
        Enum(*BUSINESS_TYPES, name="revenue_business_type", native_enum=False, create_constraint=True),
        nullable=True,
    )  # CORE or SPECIALITY

    # Partner revenue share (calculated and stored for audit trail)
    # Only applies to CORE business type
    partner_id = Column(String(512), nullable=True, index=True)  # Partner identifier (no FK - partners table TBD)
    partner_revenue_share_pct = Column(Integer, nullable=True)  # 0-100, from partner.core_revenue_share_pct
    partner_revenue_share_usd_cents = Column(Integer, nullable=True)  # Calculated as revenue * (share_pct / 100)

    # Gross margin tracking (cost per invoice derived from employee rates + hours)
    cost_usd_cents = Column(Integer, nullable=True)
    gross_margin_usd_cents = Column(Integer, nullable=True)  # revenue - cost
    gross_margin_pct = Column(Integer, nullable=True)  # (gross_margin / revenue) * 100

    # Source and timing
    source = Column(
        Enum(*REVENUE_SOURCES, name="revenue_source", native_enum=False, create_constraint=True),
        nullable=False, default="INVOICE",
    )
    recognized_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id], lazy="select")
