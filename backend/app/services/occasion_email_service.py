"""Occasion emails, sent by themselves (CEO 2026-11-03: birthdays, work and marriage anniversaries, project milestones,
appreciation; "for candidate it is sent from the candidate recruiter if there is not recruiter then from common mailbox.
If employee from the HR or their reporting manager").

Wording lives in Templates & Checklists (message templates, editable, with {{fields}}). A person gets one email per
occasion (OccasionEmail is unique on it). A date we do not have means no email, never a guess. Candidate dates of birth
are only known when volunteered or collected after an offer: Thunder does not ask for them.
"""
import html
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.occasion_email import OccasionEmail
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import Users

logger = logging.getLogger(__name__)

CANDIDATE_BIRTHDAY = "OCCASION_CANDIDATE_BIRTHDAY"
EMPLOYEE_BIRTHDAY = "OCCASION_EMPLOYEE_BIRTHDAY"
WORK_ANNIVERSARY = "OCCASION_WORK_ANNIVERSARY"
MARRIAGE_ANNIVERSARY = "OCCASION_MARRIAGE_ANNIVERSARY"
PROJECT_MILESTONE = "OCCASION_PROJECT_MILESTONE"
APPRECIATION = "OCCASION_APPRECIATION"
MILESTONE_MONTHS = 6  # a project milestone every this many months on an allocation
_SIGN = "\n\nWarm regards,\n{{sender_name}}\n{{company_name}}"
OCCASION_TEMPLATES: Dict[str, Dict[str, str]] = {
    CANDIDATE_BIRTHDAY: {"name": "Occasion: candidate birthday", "subject": "Happy birthday, {{first_name}}",
                         "body": "Hi {{first_name}},\n\nWishing you a very happy birthday and a great year ahead." + _SIGN},
    EMPLOYEE_BIRTHDAY: {"name": "Occasion: employee birthday", "subject": "Happy birthday, {{first_name}}",
                        "body": "Hi {{first_name}},\n\nHappy birthday from all of us. Thank you for everything you bring to the team." + _SIGN},
    WORK_ANNIVERSARY: {"name": "Occasion: work anniversary", "subject": "Happy {{years}}-year work anniversary, {{first_name}}",
                       "body": "Hi {{first_name}},\n\nToday marks {{years}} year(s) with {{company_name}}. Thank you for your work and commitment." + _SIGN},
    MARRIAGE_ANNIVERSARY: {"name": "Occasion: marriage anniversary", "subject": "Happy anniversary, {{first_name}}",
                           "body": "Hi {{first_name}},\n\nWishing you and your family a very happy anniversary." + _SIGN},
    PROJECT_MILESTONE: {"name": "Occasion: project milestone", "subject": "{{months}} months on {{project_name}}, thank you",
                        "body": "Hi {{first_name}},\n\nYou have now spent {{months}} months on {{project_name}}. Thank you for what you have delivered." + _SIGN},
    APPRECIATION: {"name": "Occasion: appreciation", "subject": "Thank you, {{first_name}}",
                   "body": "Hi {{first_name}},\n\n{{note}}" + _SIGN},
}


def _is_today(day: Optional[date], today: date) -> bool:
    """Same month and day; 29 February is celebrated on 28 February in other years."""
    if day is None:
        return False
    if (day.month, day.day) == (2, 29) and today.month == 2:
        leap = today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
        return today.day == (29 if leap else 28)
    return (day.month, day.day) == (today.month, today.day)


def _hr_lead(db: Session, tenant_id) -> Optional[str]:
    """The most senior person in the HR function."""
    from app.core import authority
    from app.models.org_structure import Department

    department = db.query(Department).filter(Department.tenant_id == tenant_id, Department.active.is_(True),
                                              func.lower(Department.name) == "hr").first()
    if department is None:
        return None
    people = db.query(Users).filter(Users.department_id == department.id, Users.terminated_at.is_(None)).all()
    return max(people, key=lambda u: authority.level(db, u)).UserID if people else None


def _company(db: Session, tenant_id) -> str:
    tenant = db.get(Tenant, tenant_id) if tenant_id else None
    return tenant.name if tenant is not None else "our company"


def _send(db: Session, *, person_id: str, tenant_id, to_email: str, kind: str, occasion_key: str, on: date,
          responsible: List[Optional[str]], variables: Dict[str, str]) -> bool:
    """Send once from the first responsible person with Outlook connected, else the common mailbox. True when sent."""
    from app.services import mail_sender
    from app.services.candidate_status_notifications import seed_templates
    from app.services.message_template_service import render_template

    if db.query(OccasionEmail.id).filter_by(person_id=person_id, kind=kind, occasion_key=occasion_key).first():
        return False
    if seed_templates(db, tenant_id):  # a tenant that predates a template gets it
        db.flush()
    key = f"occasion-{kind}-{person_id}-{occasion_key}"[:255]
    sender = mail_sender.sender_for(db, key, responsible, tenant_id=tenant_id)
    people = [db.get(Users, r) for r in responsible if r]
    sender_user = next((u for u in people if u is not None and u.UserEmail and u.UserEmail.lower() == sender.mailbox.lower()), None)
    fields = {"company_name": _company(db, tenant_id), **variables,
              "sender_name": (sender_user.UserName if sender_user else None) or f"The {_company(db, tenant_id)} team"}
    rendered = render_template(db, kind, "EMAIL", str(tenant_id), fields)
    body = "<br>".join(html.escape(line) for line in rendered["rendered_body"].split("\n"))
    draft_id, _, internet_id = sender.create_draft(to_email, rendered["rendered_subject"], body, key)
    db.add(OccasionEmail(person_id=person_id, kind=kind, occasion_key=occasion_key, occasion_date=on, sent_from=sender.mailbox))
    db.commit()  # recorded before the send: a failure afterwards never means a second wish
    sender.send(draft_id)
    mail_sender.record_sent(db, key, internet_id)
    db.commit()
    return True


def _employee_occasions(db: Session, employee: Employee, today: date) -> List[Dict]:
    occasions = []
    if _is_today(employee.date_of_birth, today):
        occasions.append({"kind": EMPLOYEE_BIRTHDAY, "key": str(today.year), "fields": {}})
    if employee.joining_date and _is_today(employee.joining_date, today) and today.year > employee.joining_date.year:
        occasions.append({"kind": WORK_ANNIVERSARY, "key": str(today.year), "fields": {"years": str(today.year - employee.joining_date.year)}})
    if _is_today(employee.marriage_date, today):
        occasions.append({"kind": MARRIAGE_ANNIVERSARY, "key": str(today.year), "fields": {}})
    allocations = db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status == "ACTIVE").all()
    for allocation in allocations:
        if not allocation.start_date or allocation.start_date.day != today.day:
            continue
        months = (today.year - allocation.start_date.year) * 12 + today.month - allocation.start_date.month
        if months > 0 and months % MILESTONE_MONTHS == 0:
            project_row = db.get(Project, allocation.project_id) if allocation.project_id else None
            project = project_row.name if project_row is not None else (allocation.role or "your project")
            occasions.append({"kind": PROJECT_MILESTONE, "key": f"{allocation.id}-{months}", "fields": {"months": str(months), "project_name": project}})
    return occasions


def run_occasion_emails_job(db: Session, *, today: Optional[date] = None) -> Dict[str, int]:
    """Today's occasions for everyone. One person's failure never stops the others; it is retried tomorrow only if the
    date still matches, so it is logged as an error. Commits per person."""
    from app.services.thunder_mail.candidate_notices import may_email

    today = today or date.today()
    sent = failed = 0
    for employee in db.query(Employee).filter(Employee.status.notin_(("EXITED", "PRE_JOINING"))).all():
        for occasion in _employee_occasions(db, employee, today):
            responsible = [employee.reporting_manager_user_id, _hr_lead(db, employee.tenant_id)]
            try:
                sent += _send(db, person_id=employee.id, tenant_id=employee.tenant_id, to_email=employee.email, kind=occasion["kind"],
                              occasion_key=occasion["key"], on=today, responsible=responsible,
                              variables={"first_name": employee.first_name or "there", **occasion["fields"]})
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.error(f"[Occasion] {occasion['kind']} for employee {employee.id}: {exc}", exc_info=True)
    archived = {r[0] for r in db.query(CandidateStatus.candidateID).filter(CandidateStatus.status == "Inactive")}
    employees = {r[0] for r in db.query(Employee.candidate_id).filter(Employee.candidate_id.isnot(None))}
    candidates = db.query(Candidate).filter(Candidate.candidateDateOfBirth.isnot(None), Candidate.merged_into_id.is_(None)).all()
    for candidate in candidates:
        if candidate.candidateID in archived or candidate.candidateID in employees or not _is_today(candidate.candidateDateOfBirth, today):
            continue
        allowed, reason = may_email(db, candidate, CANDIDATE_BIRTHDAY)
        if not allowed:
            logger.info(f"[Occasion] {candidate.candidateID} birthday not sent: {reason}")
            continue
        try:
            sent += _send(db, person_id=candidate.candidateID, tenant_id=candidate.tenant_id, to_email=candidate.candidateEmail,
                          kind=CANDIDATE_BIRTHDAY, occasion_key=str(today.year), on=today, responsible=[candidate.assigned_recruiter_id],
                          variables={"first_name": candidate.candidateFirstName or "there"})
        except Exception as exc:
            db.rollback()
            failed += 1
            logger.error(f"[Occasion] birthday for candidate {candidate.candidateID}: {exc}", exc_info=True)
    logger.info(f"[Occasion] {today}: {sent} sent, {failed} failed")
    return {"sent": sent, "failed": failed}


def send_appreciation(db: Session, employee: Employee, actor: Users, note: str) -> bool:
    """A manager thanks someone: from their own Outlook when connected, in their words."""
    note = (note or "").strip()
    if len(note) < 10:
        raise ValueError("Say what the thanks is for, in at least 10 characters.")
    return _send(db, person_id=employee.id, tenant_id=employee.tenant_id, to_email=employee.email, kind=APPRECIATION,
                 occasion_key=datetime.utcnow().strftime("%Y%m%d%H%M%S"), on=date.today(), responsible=[actor.UserID],
                 variables={"first_name": employee.first_name or "there", "note": note})
