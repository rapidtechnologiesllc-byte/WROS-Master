"""One employee's whole record for the profile page (CEO 2026-10-24): who they are, their job and
reporting line, where they are deployed, their programs and certificates, money, where they came
from (candidate, offer, background check, onboarding checklist, referral) and their history.

What a viewer sees follows their role template only:
- compensation (salary, loaded cost inputs) needs finance-operations.view (the fully-loaded-cost rule)
- government ids are masked to the last 4 characters; bank details never leave the server
"""
import json
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core import authority
from app.models.employee import (EMPLOYMENT_TYPES, WORK_LOCATIONS, Employee, EmployeeEmploymentHistory,
                                 EmployeeEngineHistory)
from app.models.client import BILLING_CURRENCIES
from app.models.user import Users
from app.services.compensation import PAY_BASES


def mask(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return "•" * max(0, len(value) - 4) + value[-4:]


def can_see_compensation(db: Session, viewer: Users) -> bool:
    return authority.has_permission(db, viewer, "finance-operations.view")


def can_edit_compensation(db: Session, viewer: Users) -> bool:
    return authority.has_permission(db, viewer, "finance-operations.edit")


def _user_ref(user: Optional[Users], employee_ids: dict) -> Optional[dict]:
    if user is None:
        return None
    return {"user_id": user.UserID, "name": user.UserName or user.UserEmail,
            "employee_id": employee_ids.get(user.UserID)}


def _history(db: Session, employee: Employee) -> list:
    """Every recorded change, newest first: status / org moves (employment history) and engine moves."""
    events = []
    for row in db.query(EmployeeEmploymentHistory).filter(EmployeeEmploymentHistory.employee_id == employee.id).all():
        def parsed(raw):
            try:
                return json.loads(raw) if raw else None
            except (TypeError, ValueError):
                return raw  # free text kept as written
        events.append({"kind": row.change_type, "date": row.effective_date.isoformat() if row.effective_date else None,
                       "from": parsed(row.old_value), "to": parsed(row.new_value), "reason": row.reason,
                       "by": row.changed_by})
    for row in db.query(EmployeeEngineHistory).filter(EmployeeEngineHistory.employee_id == employee.id).all():
        events.append({"kind": "ENGINE", "date": row.changed_at.date().isoformat() if row.changed_at else None,
                       "from": row.from_engine, "to": row.to_engine, "reason": row.reason, "by": row.changed_by})
    return sorted(events, key=lambda e: e["date"] or "", reverse=True)


def _origin(db: Session, employee: Employee) -> Optional[dict]:
    """Where the employee came from: the candidate record and what hiring produced."""
    if not employee.candidate_id:
        return None
    from app.models.background_verification import BackgroundVerification
    from app.models.candidate import Candidate
    from app.models.checklist import CandidateChecklist
    from app.models.offer_letter import OfferLetter

    candidate = db.query(Candidate).filter(Candidate.candidateID == employee.candidate_id).first()
    if candidate is None:
        return {"candidate_id": employee.candidate_id, "missing": True}
    recruiter = db.query(Users).filter(Users.UserID == candidate.assigned_recruiter_id).first() \
        if candidate.assigned_recruiter_id else None
    offer = db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate.candidateID) \
        .order_by(OfferLetter.created_at.desc()).first()
    bgv = db.query(BackgroundVerification).filter(BackgroundVerification.candidate_id == candidate.candidateID) \
        .order_by(BackgroundVerification.created_at.desc()).first()
    checklists = db.query(CandidateChecklist).filter(CandidateChecklist.candidate_id == candidate.candidateID).all()
    return {
        "candidate_id": candidate.candidateID,
        "source": candidate.recruitment_source or candidate.candidateSource,
        "applied_for": candidate.candidateJobTitle,
        "recruiter": recruiter.UserName if recruiter else None,
        "referred": candidate.referral_id is not None,
        "linkedin_url": candidate.linkedin_url,
        "offer": {"status": offer.offer_status, "joining_date": offer.joining_date.isoformat() if offer.joining_date else None,
                  "released_at": offer.released_at.isoformat() if offer.released_at else None,
                  "document_url": offer.download_url or offer.sharepoint_url} if offer else None,
        "background_check": {"status": bgv.status, "verdict_at": bgv.verdict_at.isoformat() if bgv.verdict_at else None,
                             "report_url": bgv.report_url} if bgv else None,
        "checklists": [{"id": c.id, "status": c.status,
                        "completed_at": c.completed_at.isoformat() if c.completed_at else None} for c in checklists],
    }


def build_profile(db: Session, employee: Employee, viewer: Users, item: dict) -> dict:
    """item: the employee's list item (EmployeeItem as dict): status, deployment, allocations."""
    from app.models.business_unit import BusinessUnit
    from app.models.location import Location
    from app.services.org_structure_service import manager_user_for

    manager = manager_user_for(db, employee)
    team = db.query(Employee).filter(Employee.tenant_id == employee.tenant_id,
                                     Employee.reporting_manager_user_id == employee.wros_user_id,
                                     Employee.status != "EXITED").all() if employee.wros_user_id else []
    login_ids = {u for u in [manager.UserID if manager else None] if u}
    employee_ids = {e.wros_user_id: e.id for e in db.query(Employee.wros_user_id, Employee.id)
                    .filter(Employee.wros_user_id.in_(login_ids))} if login_ids else {}
    company = db.query(Location).filter(Location.id == employee.company_id).first() if employee.company_id else None
    unit = db.query(BusinessUnit).filter(BusinessUnit.id == employee.bu_id).first() if employee.bu_id else None
    sees_money = can_see_compensation(db, viewer)

    return {
        **item,
        "can_edit": authority.has_permission(db, viewer, "employees.edit"),
        "can_edit_compensation": can_edit_compensation(db, viewer),
        "options": {"work_locations": list(WORK_LOCATIONS), "employment_types": list(EMPLOYMENT_TYPES),
                    "pay_bases": list(PAY_BASES), "currencies": list(BILLING_CURRENCIES)},
        "personal": {
            "legal_name": employee.legal_name, "personal_email": employee.personal_email, "phone": employee.phone,
            "date_of_birth": employee.date_of_birth.isoformat() if employee.date_of_birth else None,
            "gender": employee.gender, "nationality": employee.nationality,
            "current_address": employee.current_address, "permanent_address": employee.permanent_address,
            "emergency_contact_name": employee.emergency_contact_name,
            "emergency_contact_phone": employee.emergency_contact_phone,
        },
        "job": {
            "employee_number": employee.employee_number,
            "company_name": company.name if company else None,
            "business_unit_name": unit.name if unit else None,
            "reporting_manager": _user_ref(manager, employee_ids),
            "confirmation_date": employee.confirmation_date.isoformat() if employee.confirmation_date else None,
            "visa_status": employee.visa_status,
            "total_experience_months": employee.total_experience_months,
            "blitzenx_experience_months": employee.blitzenx_experience_months,
            "delivery_engine": employee.delivery_engine,
            "core_certified": bool(employee.core_certified),
        },
        "reporting_team": [{"employee_id": e.id, "name": f"{e.first_name} {e.last_name}".strip(),
                            "title": e.current_title} for e in team],
        "programs": {
            "buddy_program_status": employee.buddy_program_status,
            "buddy_program_start_date": employee.buddy_program_start_date.isoformat() if employee.buddy_program_start_date else None,
            "buddy_program_graduation_date": employee.buddy_program_graduation_date.isoformat()
            if employee.buddy_program_graduation_date else None,
        },
        "finance": {
            "base_salary_usd_cents": employee.base_salary_usd_cents if sees_money else None,
            "pay_amount_cents": employee.pay_amount_cents if sees_money else None,
            "pay_currency": employee.pay_currency if sees_money else None,
            "pay_basis": employee.pay_basis if sees_money else None,
            "compensation_visible": sees_money,
            "billing_rate_usd_cents": employee.billing_rate_usd_cents,
            "billing_classification": employee.billing_classification,
            "pan_number": mask(employee.pan_number),
            "tax_id": mask(employee.tax_id),
            "bank_on_file": bool(employee.bank_account_number_encrypted),
        },
        "origin": _origin(db, employee),
        "history": _history(db, employee),
        "as_of": date.today().isoformat(),
    }
