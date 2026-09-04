"""
HRMS-P801 (Registration & Onboarding) + HRMS-P804/P811 (Demand
assignment / request lifecycle).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.demand import Demand
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest, SubVendorUser


class SubVendorNotApproved(Exception):
    """HRMS-P801 BR-01: no submission (or request assignment) until status=APPROVED."""


def register_sub_vendor(
    db: Session, *, tenant_id: Optional[int], company_name: str, contact_email: str,
    contact_phone: Optional[str] = None, tax_id: Optional[str] = None,
) -> SubVendorAccount:
    account = SubVendorAccount(
        tenant_id=tenant_id, company_name=company_name, contact_email=contact_email,
        contact_phone=contact_phone, tax_id=tax_id,
    )
    db.add(account)
    return account


def approve_sub_vendor(db: Session, account: SubVendorAccount, *, approved_by: str) -> SubVendorAccount:
    account.status = "APPROVED"
    account.approved_by = approved_by
    account.approved_at = datetime.utcnow()
    db.add(account)
    return account


def suspend_sub_vendor(db: Session, account: SubVendorAccount) -> SubVendorAccount:
    account.status = "SUSPENDED"
    db.add(account)
    return account


def is_approved_for_submission(account: SubVendorAccount) -> bool:
    """The actual gate: HRMS-P801 BR-01, no submission until APPROVED,
    and HRMS-P811 BR-0811-02, a SUSPENDED/SUSPENSION_PENDING compliance
    standing also blocks new submissions even if registration remains
    APPROVED."""
    return account.status == "APPROVED" and account.compliance_status not in ("SUSPENDED", "SUSPENSION_PENDING")


def create_sub_vendor_user(
    db: Session, account: SubVendorAccount, *, name: str, email: str, plain_password: str, role: str = "SUBMITTER",
) -> SubVendorUser:
    user = SubVendorUser(
        sub_vendor_id=account.id, name=name, email=email,
        password_hash=get_password_hash(plain_password), role=role,
    )
    db.add(user)
    return user


def create_sub_vendor_request(
    db: Session, *, tenant_id: Optional[int], demand: Demand, sub_vendor: SubVendorAccount,
    assigned_by: Optional[str] = None, deadline=None, max_candidates: Optional[int] = None,
) -> SubVendorRequest:
    """HRMS-P804 BR-01: sub-vendors see only explicitly assigned demands
    -- no general browsing. Only an APPROVED vendor can be assigned a
    request at all."""
    if not is_approved_for_submission(sub_vendor):
        raise SubVendorNotApproved(
            f"Sub-vendor {sub_vendor.id} is not approved for new requests "
            f"(status={sub_vendor.status}, compliance_status={sub_vendor.compliance_status})."
        )

    request = SubVendorRequest(
        tenant_id=tenant_id, demand_id=demand.id, sub_vendor_id=sub_vendor.id,
        assigned_by=assigned_by, deadline=deadline, max_candidates=max_candidates,
    )
    db.add(request)
    return request


def close_expired_requests(db: Session, *, now: Optional[datetime] = None) -> int:
    """
    HRMS-P811 BR-0811-01: deadline closure is fully automatic, no
    approval gate -- a low-risk, reversible administrative action (a
    recruiter can manually reopen a request if needed; reopening itself
    isn't built here, out of scope for this pass). Not wired to a
    scheduler -- the function a cron would call, same posture as every
    other scheduled job this session.
    """
    now = now or datetime.utcnow()
    expired = db.query(SubVendorRequest).filter(
        SubVendorRequest.status == "OPEN",
        SubVendorRequest.deadline.isnot(None),
        SubVendorRequest.deadline <= now,
    ).all()
    for request in expired:
        request.status = "CLOSED"
        db.add(request)
    return len(expired)
