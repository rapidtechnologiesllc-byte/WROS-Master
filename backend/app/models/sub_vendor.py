"""
HRMS-P801 -- Sub-Vendor Portal, Registration & Onboarding. Phase 2
Domain 5, greenfield (nothing in this codebase to extend/fork, unlike
import logging
Client/Demand).

Table name: the corpus itself is inconsistent -- P801's own CREATE
TABLE calls it `sub_vendors`, while P811/P812 and 02-DATA-MODEL.md's
sketch call it `sub_vendor_accounts`. Went with `sub_vendor_accounts`
(matches the data-model sketch and the richer, later doc batch).

Two status fields, not a conflict to pick between: P801 defines a
registration-approval lifecycle (`status`: PENDING_APPROVAL/APPROVED/
SUSPENDED/REJECTED) and P811 defines an ongoing compliance-standing
lifecycle (`compliance_status`: GOOD_STANDING/UNDER_REVIEW/
SUSPENSION_PENDING/SUSPENDED) -- these are genuinely different
concerns (can a vendor use the portal at all, vs. are they currently in
good standing), modeled as two separate columns on the same table
rather than merging into one enum.

Login is explicitly email+password, NOT magic link, per P801's own
"sub-vendors are business accounts, not candidates" note -- SubVendorUser
is a separate account space from the internal `users` table.
"""
import logging
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer,
    String, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


SUBVENDOR_STATUSES = ("PENDING_APPROVAL", "APPROVED", "SUSPENDED", "REJECTED")
SUBVENDOR_COMPLIANCE_STATUSES = ("GOOD_STANDING", "UNDER_REVIEW", "SUSPENSION_PENDING", "SUSPENDED")
SUBVENDOR_USER_ROLES = ("ADMIN", "SUBMITTER")

logger = logging.getLogger(__name__)

class SubVendorAccount(Base):
    __tablename__ = "sub_vendor_accounts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    company_name = Column(String(300), nullable=False)
    tax_id = Column(String(512), nullable=True)
    contact_email = Column(String(300), nullable=False)
    contact_phone = Column(String(512), nullable=True)

    # HRMS-P801 BR-01: registration lifecycle -- no submission until APPROVED.
    status = Column(
        Enum(*SUBVENDOR_STATUSES, name="subvendor_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING_APPROVAL",
    )
    # HRMS-P811: ongoing compliance standing, separate from registration status.
    compliance_status = Column(
        Enum(*SUBVENDOR_COMPLIANCE_STATUSES, name="subvendor_compliance_status", native_enum=False, create_constraint=True),
        nullable=False, default="GOOD_STANDING",
    )

    approved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())


class SubVendorRequest(Base):
    """
    HRMS-P804 (Sub-Vendor Demand Visibility) merged with the richer
    "request" concept P811's governance agent and P814's clarification
    Q&A both assume (deadline tracking, auto-close) -- P804's own
    `demand_subvendor_assignments` sketch has no deadline/status fields
    at all, which can't support either downstream story. Treating P804
    as the earlier/thinner draft this supersedes, not a separate table.
    """
    __tablename__ = "sub_vendor_requests"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)

    assigned_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    assigned_at = Column(DateTime, server_default=func.now())
    deadline = Column(DateTime, nullable=True)
    max_candidates = Column(Integer, nullable=True)

    # HRMS-P811 BR-0811-01: auto-closes at deadline, no approval gate --
    # a low-risk, reversible administrative action.
    status = Column(
        Enum("OPEN", "CLOSED", name="subvendor_request_status", native_enum=False, create_constraint=True),
        nullable=False, default="OPEN",
    )


class ClarificationQA(Base):
    """
    HRMS-P814 -- vendor asks a question against a specific request;
    visible to every vendor viewing that request, not just the asker
    (BR-0814-01) -- a clarification answered once shouldn't need
    re-asking. Min length: question >= 10 chars, answer >= 10 chars,
    enforced in app.services.sub_vendor_qa_service.
    """
    __tablename__ = "clarification_qa"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    request_id = Column(String(512), ForeignKey("sub_vendor_requests.id"), nullable=False, index=True)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)

    question = Column(String(2000), nullable=False)
    asked_at = Column(DateTime, server_default=func.now())

    answer = Column(String(2000), nullable=True)
    answered_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    answered_at = Column(DateTime, nullable=True)


class SubVendorUser(Base):
    __tablename__ = "sub_vendor_users"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)

    name = Column(String(512), nullable=False)
    email = Column(String(300), nullable=False, unique=True, index=True)
    password_hash = Column(String(300), nullable=False)
    role = Column(
        Enum(*SUBVENDOR_USER_ROLES, name="subvendor_user_role", native_enum=False, create_constraint=True),
        nullable=False, default="SUBMITTER",
    )
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now())
