"""
import logging
HRMS-0102 — Client Entity Model, Phase 2 Domain 4.

Same SQL-Server/SQLite-portable translation conventions as
app.models.employee: UUID as String(36), Enum(native_enum=False, create_constraint=True).

HRMS-0201 ("Client Entity Management v2") is a genuine architectural
fork of this same concept -- same pattern as the earlier EPIC-01-vs-
EPIC-07 Submission Pipeline fork. It depends only on HRMS-0109, never
mentions HRMS-0102, and specifies a differently-shaped clients table
(name/industry/country/default_currency/account_manager only -- no
client_type/tier/status/billing fields/markup_rate/nda, notes routed
through a shared Activity Timeline table instead of the client_history
audit table below). Since this model is already load-bearing (Demand,
Submission, EmployeeAllocation, etc. all FK to it), this session
extends it rather than forking: added `country` (genuinely new, HRMS-
0201 introduces it), reused `billing_currency` for HRMS-0201's
"default_currency" concept (same idea, don't duplicate), and added
HRMS-0201's one real new business rule -- exactly one primary contact,
enforced transactionally, see set_primary_contact() in
app.services.client_service. Kept `client_history`/`notes` as-is rather
than migrating to HRMS-0118's Activity Timeline (which doesn't exist in
this codebase) -- and kept ClientContact.role_type's existing, more
specific enum (HIRING_MANAGER/TECHNICAL_PANEL/PROCUREMENT/ACCOUNTS/
PRIMARY) rather than adopting HRMS-0201's coarser vocabulary
(Decision Maker/Day-to-Day/Finance), since the two don't map 1:1 and
picking one is a product call, not an engineering one -- flagged here,
not silently resolved.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


CLIENT_TYPES = ("DIRECT", "MSP", "VMS")
CLIENT_TIERS = ("PLATINUM", "GOLD", "SILVER", "STANDARD")
# Shared with Opportunity.stage - single source of truth
# If stages change, update both here and app.models.opportunity
PIPELINE_STATUSES = ("QUALIFICATION", "PROSPECT", "PROPOSAL", "NEGOTIATION", "CONTRACT", "ACTIVE", "LOST")
CLIENT_STATUSES = PIPELINE_STATUSES  # Client.status uses same values as Opportunity.stage
BILLING_CURRENCIES = ("USD", "INR", "GBP", "EUR", "CAD", "AUD")
CONTACT_ROLE_TYPES = ("HIRING_MANAGER", "TECHNICAL_PANEL", "PROCUREMENT", "ACCOUNTS", "PRIMARY", "TIMESHEET_APPROVER")

# 2026-08-06, confirmed directly with Avinash while redesigning Client
# Management live: the same Core/Specialty split as Employee.delivery_
# engine, not a new taxonomy -- matches the real FY26-27 workbook's
# Line Type field. Replaces client_type on the create form (client_type
# itself is kept, unenforced, only for legacy rows created before this
# -- new clients set line_type instead; see client_service.create_client()).
LINE_TYPES = ("CORE", "SPECIALITY")

# BR-01: cannot set status=ACTIVE without at least one client_contact.
STATUSES_REQUIRING_CONTACT = {"ACTIVE"}

logger = logging.getLogger(__name__)

class Client(Base):
    __tablename__ = "clients"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # EPIC-02/03 access spec, 2026-08-05 -- Avinash's own words: "a
    # partner has it's own clients and the work is done in their BU
    # only... any business he generates should go only to that BU."
    # The client itself is the real point of BU ownership -- every
    # Opportunity/Demand/revenue figure under this client inherits it
    # by joining through here, never a second, independently-settable
    # copy on Opportunity (single source of truth, no drift risk).
    # Nullable: a prospect with no partner/BU assigned yet is visible
    # to everyone until claimed, same "Org Pool" posture
    # CandidateOwnership already established for candidates.
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    company_name = Column(String(300), nullable=False)
    company_short_name = Column(String(512), nullable=True)
    industry = Column(String(512), nullable=True)
    # HRMS-0201 -- genuinely new field this story adds; HRMS-0102 had no
    # country column (only free-text billing_address). See module-level
    # note below on why this extends HRMS-0102 rather than forking it.
    country = Column(String(512), nullable=True)
    client_type = Column(Enum(*CLIENT_TYPES, name="client_type", native_enum=False, create_constraint=True), nullable=False, default="DIRECT")
    # 2026-08-06 -- see LINE_TYPES above. Nullable because existing rows
    # predate this field; the create form requires it going forward.
    line_type = Column(Enum(*LINE_TYPES, name="client_line_type", native_enum=False, create_constraint=True), nullable=True)
    # 2026-08-06 -- real dedup key, same precedent as
    # create_candidate_safe()'s email/phone/LinkedIn checks. Not a DB
    # UNIQUE constraint (existing rows may already collide on a blank/
    # duplicate value) -- enforced in client_service.create_client()
    # the same way email dedup is app-level there, not DB-level.
    website = Column(String(300), nullable=True)
    tier = Column(Enum(*CLIENT_TIERS, name="client_tier", native_enum=False, create_constraint=True), nullable=False, default="STANDARD")
    status = Column(Enum(*CLIENT_STATUSES, name="client_status", native_enum=False, create_constraint=True), nullable=False, default="PROSPECT")

    account_manager_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True)

    billing_address = Column(Text, nullable=True)
    billing_currency = Column(Enum(*BILLING_CURRENCIES, name="billing_currency", native_enum=False, create_constraint=True), nullable=False, default="USD")
    payment_terms_days = Column(Integer, nullable=False, default=30)
    credit_limit_usd_cents = Column(Integer, nullable=True)
    tax_id_client = Column(String(512), nullable=True)

    contract_start_date = Column(Date, nullable=True)
    contract_end_date = Column(Date, nullable=True)
    contract_url = Column(Text, nullable=True)

    # BR-02: confidential -- see app.core.tenant_context-style access
    # guard needed at the API layer (not yet wired to any route; the
    # model just holds the field). Never serialize this to a CS/
    # recruiter-facing response.
    markup_rate_pct = Column(Numeric(5, 2), nullable=True)

    nda_signed = Column(Boolean, nullable=False, default=False)
    nda_url = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(String(512), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    contacts = relationship("ClientContact", back_populates="client", lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "company_name", name="uq_client_company_name_per_tenant"),
    )


class ClientContact(Base):
    __tablename__ = "client_contacts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)

    name = Column(String(512), nullable=False)
    title = Column(String(512), nullable=True)
    email = Column(String(300), nullable=False)
    phone = Column(String(512), nullable=True)
    role_type = Column(Enum(*CONTACT_ROLE_TYPES, name="contact_role_type", native_enum=False, create_constraint=True), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    linkedin_url = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="contacts", lazy="select")

    __table_args__ = (
        UniqueConstraint("client_id", "email", name="uq_client_contact_email_per_client"),
    )


class ClientHistory(Base):
    """Insert-only, same immutable pattern as employee_employment_history."""
    __tablename__ = "client_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    change_type = Column(
        Enum("STATUS", "ACCOUNT_MANAGER", "TIER", "CONTRACT_TERMS", name="client_change_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(512), nullable=True)
    changed_at = Column(DateTime, server_default=func.now())
