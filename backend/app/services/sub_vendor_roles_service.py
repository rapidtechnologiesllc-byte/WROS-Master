"""Sub-vendors hear about new roles and submit candidates by email (CEO 2026-11-03: "how we notify sub vendor of
new roles that they can submit candidates").

- New role: a client job that opens is sent once to every approved sub-vendor in good standing that receives new
  roles (SubVendorAccount.receives_new_roles), from the job's recruiter's own Outlook. The email carries the role,
  skills, location and experience; never the client's name, the bill rate or the salary. Only jobs opened in the
  last SUB_VENDOR_ROLE_WINDOW_DAYS go out, so older open jobs are never sent in one blast.
- Submission: the vendor replies with a resume. It is recorded against that role as PENDING_REVIEW and the recruiter
  gets one task, because whether to take a vendor's candidate is their decision.
- Accept: the candidate is created through the one candidate path (or the existing record is linked) with the
  sub-vendor as source. Thunder is not started: the candidate belongs to the vendor's relationship.
- Reject: the reason is required and goes back to the vendor on their email.
"""
import base64
import html
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest
from app.models.sub_vendor_submission import SubVendorSubmission
from app.models.user import Jobs, Users

logger = logging.getLogger(__name__)

OPEN_JOB_STATUSES = ("active", "public")
ROLE_REF_PATTERN = re.compile(r"\[Role ([0-9a-f]{8})\]", re.I)
MIN_REJECTION_NOTE = 20


class SubVendorSubmissionError(ValueError):
    """A submission rule was not met; the message says which."""


def _without_client(text: str, client_name: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(re.escape(client_name), "our client", text, flags=re.I) if client_name else text


def role_email(job: Jobs, request: SubVendorRequest, client_name: Optional[str]) -> Dict[str, str]:
    """The subject and body of a new-role email. The client's name never appears."""
    title = _without_client(job.jobTitle, client_name)
    rows = [("Location", job.jobLocation), ("Experience", job.jobExperience), ("Skills", job.jobSkills),
            ("Positions", job.noOfPositions)]
    details = "".join(f"<li><b>{label}:</b> {html.escape(_without_client(str(value), client_name))}</li>"
                      for label, value in rows if value)
    description = html.escape(_without_client(job.jobDescription or "", client_name))[:3000].replace("\n", "<br>")
    body = (f"<p>We have a new role open and would welcome your candidates.</p><p><b>{html.escape(title)}</b></p>"
            f"<ul>{details}</ul><p>{description}</p>"
            "<p>To submit a candidate, reply to this email with their resume attached.</p>")
    return {"subject": f"New role: {title} [Role {request.id[:8]}]", "html": body}


def _eligible_vendors(db: Session, tenant_id: Optional[int]) -> List[SubVendorAccount]:
    return db.query(SubVendorAccount).filter(
        SubVendorAccount.tenant_id == tenant_id, SubVendorAccount.status == "APPROVED",
        SubVendorAccount.compliance_status == "GOOD_STANDING", SubVendorAccount.receives_new_roles.is_(True)).all()


def _send_role(db: Session, job: Jobs, vendor: SubVendorAccount, request: SubVendorRequest, mailbox=None) -> None:
    from app.services import mail_sender

    client = db.get(Client, job.client_id)
    email = role_email(job, request, client.company_name if client is not None else None)
    key = f"sub-vendor-role-{request.id}"
    sender = mailbox or mail_sender.sender_for(db, key, [job.recuriterID, job.contactPerson, job.hiringManagerID],
                                               tenant_id=vendor.tenant_id)
    draft_id, _, internet_id = sender.create_draft(vendor.contact_email, email["subject"], email["html"], key)
    sender.send(draft_id)
    mail_sender.record_sent(db, key, internet_id)
    request.notified_at = datetime.utcnow()


def run_new_roles_job(db: Session, *, now: Optional[datetime] = None, mailbox=None) -> Dict:
    """Send each newly opened client job to the sub-vendors that have not had it; close requests past their deadline.
    Commits per email, so one failure never re-sends the others."""
    from app.services.sub_vendor_service import close_expired_requests

    now = now or datetime.utcnow()
    closed = close_expired_requests(db, now=now)
    db.commit()
    since = now - timedelta(days=settings.SUB_VENDOR_ROLE_WINDOW_DAYS)
    jobs = db.query(Jobs).filter(Jobs.jobStatus.in_(OPEN_JOB_STATUSES), Jobs.client_id.isnot(None),
                                 Jobs.jobCreatedAt >= since).all()
    sent, failed = 0, []
    for job in jobs:
        for vendor in _eligible_vendors(db, job.tenant_id):
            request = db.query(SubVendorRequest).filter(SubVendorRequest.demand_id == job.jobID,
                                                        SubVendorRequest.sub_vendor_id == vendor.id).first()
            if request is not None and request.notified_at is not None:
                continue
            try:
                if request is None:
                    request = SubVendorRequest(tenant_id=job.tenant_id, demand_id=job.jobID, sub_vendor_id=vendor.id)
                    db.add(request)
                    db.flush()
                _send_role(db, job, vendor, request, mailbox)
                db.commit()
                sent += 1
            except Exception as exc:  # the next run retries: no notified_at was committed
                db.rollback()
                logger.error(f"[SubVendorRoles] {job.jobID} to {vendor.company_name}: {exc}", exc_info=True)
                failed.append(f"{job.jobID}/{vendor.id}")
    if failed:
        raise RuntimeError(f"{len(failed)} new-role email(s) failed and will retry: {failed[:5]} ({sent} sent)")
    logger.info(f"[SubVendorRoles] {sent} new-role email(s) sent, {closed} request(s) closed")
    return {"sent": sent, "closed": closed}


def _role_for(db: Session, vendor: SubVendorAccount, subject: str) -> Optional[SubVendorRequest]:
    """The role a vendor's email is about: its [Role ...] reference, else the job title in the subject, else the
    vendor's only open role."""
    open_requests = db.query(SubVendorRequest).filter(SubVendorRequest.sub_vendor_id == vendor.id,
                                                      SubVendorRequest.status == "OPEN").all()
    reference = ROLE_REF_PATTERN.search(subject or "")
    if reference:
        match = [r for r in open_requests if r.id.startswith(reference.group(1).lower())]
        if match:
            return match[0]
    titled = [r for r in open_requests
              if (db.get(Jobs, r.demand_id).jobTitle or "").lower() in (subject or "").lower()]
    if len(titled) == 1:
        return titled[0]
    return open_requests[0] if len(open_requests) == 1 else None


def _recruiter(job: Jobs) -> Optional[str]:
    return job.recuriterID or job.contactPerson or job.hiringManagerID


def _review_task(db: Session, vendor: SubVendorAccount, job: Optional[Jobs], title: str, description: str) -> None:
    from app.services.task_service import create_task
    from app.services.vendor_invoice_intake import vendor_payer

    create_task(db, title=title[:300], description=description[:8000], priority="HIGH", tenant_id=vendor.tenant_id,
                assigned_to_user_id=(_recruiter(job) if job is not None else None) or vendor_payer(db, vendor.tenant_id),
                category="RECRUITMENT", link="/sub-vendors?view=submissions", due_date=datetime.utcnow())


def receive_submission(db: Session, vendor: SubVendorAccount, message: Dict, attachments: List, mailbox: str) -> bool:
    """Record the resumes a sub-vendor emailed. True when the email was a submission. Commits."""
    from app.services.thunder_mail.forward_classifier import (EMAIL_PATTERN, RESUME_EXTENSIONS, _name_from_file,
                                                              _phones, join_split_emails)

    files = [a for a in attachments if a.content is not None and (a.text or "").strip()
             and a.name.lower().endswith(RESUME_EXTENSIONS)]
    if not files:
        return False
    subject = message.get("subject") or ""
    request = _role_for(db, vendor, subject)
    if request is None:
        open_roles = db.query(SubVendorRequest).filter(SubVendorRequest.sub_vendor_id == vendor.id,
                                                       SubVendorRequest.status == "OPEN").all()
        if not open_roles:
            return False  # no role was offered to them: their ordinary email
        job = db.get(Jobs, open_roles[0].demand_id)
        titles = ", ".join(db.get(Jobs, r.demand_id).jobTitle for r in open_roles[:10])
        _review_task(db, vendor, job, f"{vendor.company_name} sent a resume: which role is it for?",
                     f"\"{subject}\" ({', '.join(a.name for a in files)}) does not say which role. Their open roles: {titles}.")
        db.commit()
        return True
    job = db.get(Jobs, request.demand_id)
    vendor_domain = vendor.contact_email.split("@")[-1].lower()
    for attachment in files:
        if db.query(SubVendorSubmission.id).filter(SubVendorSubmission.graph_message_id == message.get("id"),
                                                   SubVendorSubmission.attachment_id == attachment.attachment_id).first():
            continue
        text = join_split_emails(attachment.text)
        emails = [e for e in EMAIL_PATTERN.findall(text) if not e.lower().endswith(f"@{vendor_domain}")]
        phones = _phones(text)
        name = _name_from_file(attachment.name) or attachment.name
        db.add(SubVendorSubmission(
            request_id=request.id, sub_vendor_id=vendor.id, candidate_name=name[:300],
            candidate_email=(emails[0] if emails else "")[:300], candidate_phone=phones[0] if phones else None,
            source_mailbox=mailbox, graph_message_id=message.get("id"), attachment_id=attachment.attachment_id,
            resume_name=attachment.name[:300]))
        _review_task(db, vendor, job, f"Review {vendor.company_name}'s candidate {name} for {job.jobTitle}",
                     f"Accept to create the candidate, or reject with the reason (it goes back to the vendor)."
                     + ("" if emails else " No email address was found in the resume: ask the vendor for it."))
    db.commit()
    return True


def accept_submission(db: Session, user: Users, submission: SubVendorSubmission, *, email: Optional[str] = None,
                      first_name: Optional[str] = None, last_name: Optional[str] = None, mailbox=None) -> str:
    """Create (or link) the candidate. Returns the candidate id. Commits. Thunder does not start."""
    from app.models.candidate_history import CandidateHistory
    from app.services import candidate_resume_intake as resume_intake, mail_sender
    from app.services.candidate_service import create_candidate

    if submission.status != "PENDING_REVIEW":
        raise SubVendorSubmissionError(f"This submission is already {submission.status.lower()}.")
    address = (email or submission.candidate_email or "").strip().lower()
    if "@" not in address:
        raise SubVendorSubmissionError("The candidate's email address is needed: it was not in the resume.")
    parts = submission.candidate_name.split()
    first = (first_name or (parts[0] if parts else "")).strip()
    last = (last_name or " ".join(parts[1:])).strip()
    if not first or not last:
        raise SubVendorSubmissionError("The candidate's first and last name are needed.")
    vendor = db.get(SubVendorAccount, submission.sub_vendor_id)
    request = db.get(SubVendorRequest, submission.request_id)
    job = db.get(Jobs, request.demand_id)
    candidate, is_new = create_candidate(db, email=address, mobile=submission.candidate_phone, tenant_id=vendor.tenant_id,
                                         candidateFirstName=first, candidateLastName=last,
                                         candidateSource=f"Sub-vendor: {vendor.company_name}",
                                         recruitment_source="SUBVENDOR")
    db.flush()
    submission.status, submission.created_candidate_id = "ACCEPTED", candidate.candidateID
    db.add(CandidateHistory(candidateID=candidate.candidateID, event_type="Custom",
                            note=f"Submitted by {vendor.company_name} for {job.jobTitle}; accepted by "
                                 f"{user.UserName or user.UserEmail}." + ("" if is_new else " Already in our records."),
                            performed_by_id=user.UserID, performed_by_name=user.UserName or user.UserEmail,
                            event_at=datetime.utcnow()))
    db.commit()
    if submission.graph_message_id and submission.attachment_id:
        source = mailbox or mail_sender.mailbox_for_address(db, submission.source_mailbox)
        content = base64.b64decode(source.get_attachment(submission.graph_message_id, submission.attachment_id)["contentBytes"])
        resume_intake.store_resume_document(db, candidate, submission.resume_name, content, user.UserID, user.UserID,
                                            user.UserName)
    return candidate.candidateID


def reject_submission(db: Session, user: Users, submission: SubVendorSubmission, note: str, *, mailbox=None) -> None:
    """Record the reason and tell the vendor on their own email thread. Commits."""
    from app.services import mail_sender

    if submission.status != "PENDING_REVIEW":
        raise SubVendorSubmissionError(f"This submission is already {submission.status.lower()}.")
    note = (note or "").strip()
    if len(note) < MIN_REJECTION_NOTE:
        raise SubVendorSubmissionError(f"Give the reason in at least {MIN_REJECTION_NOTE} characters: it goes to the vendor.")
    submission.status, submission.feedback_note = "REJECTED", note
    db.commit()
    if not submission.graph_message_id:
        return
    try:
        source = mailbox or mail_sender.mailbox_for_address(db, submission.source_mailbox)
        draft_id, _, _ = source.create_reply_draft(
            submission.graph_message_id, f"<p>Thank you for submitting {html.escape(submission.candidate_name)}. "
                                         f"We will not take this candidate forward: {html.escape(note)}</p>")
        source.send(draft_id)
    except Exception as exc:  # the decision is recorded; only the courtesy reply failed
        logger.error(f"[SubVendorRoles] the rejection reply for {submission.id} failed: {exc}", exc_info=True)


def roles_summary(db: Session, tenant_id: Optional[int]) -> List[Dict]:
    counts = dict(db.query(SubVendorSubmission.request_id, func.count(SubVendorSubmission.id))
                  .group_by(SubVendorSubmission.request_id))
    rows = (db.query(SubVendorRequest, Jobs, SubVendorAccount)
            .join(Jobs, Jobs.jobID == SubVendorRequest.demand_id)
            .join(SubVendorAccount, SubVendorAccount.id == SubVendorRequest.sub_vendor_id)
            .filter(SubVendorRequest.tenant_id == tenant_id).order_by(SubVendorRequest.assigned_at.desc()).limit(500).all())
    return [{"id": r.id, "job_id": j.jobID, "job_title": j.jobTitle, "sub_vendor_id": v.id, "sub_vendor_name": v.company_name,
             "status": r.status, "notified_at": r.notified_at.isoformat() if r.notified_at else None,
             "submissions": counts.get(r.id, 0)} for r, j, v in rows]


def submissions_list(db: Session, tenant_id: Optional[int]) -> List[Dict]:
    rows = (db.query(SubVendorSubmission, SubVendorRequest, Jobs, SubVendorAccount)
            .join(SubVendorRequest, SubVendorRequest.id == SubVendorSubmission.request_id)
            .join(Jobs, Jobs.jobID == SubVendorRequest.demand_id)
            .join(SubVendorAccount, SubVendorAccount.id == SubVendorSubmission.sub_vendor_id)
            .filter(SubVendorRequest.tenant_id == tenant_id).order_by(SubVendorSubmission.created_at.desc()).limit(500).all())
    return [{"id": s.id, "candidate_name": s.candidate_name, "candidate_email": s.candidate_email, "candidate_phone": s.candidate_phone,
             "job_title": j.jobTitle, "sub_vendor_name": v.company_name, "status": s.status, "feedback_note": s.feedback_note,
             "resume_name": s.resume_name, "candidate_id": s.created_candidate_id,
             "created_at": s.created_at.isoformat() if s.created_at else None} for s, _, j, v in rows]
