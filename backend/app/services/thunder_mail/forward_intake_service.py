"""Emails staff forward to the HRMS mailbox (settings.THUNDER_MAILBOX) become HR records.

poll_thunder_mailbox stores every email from an active staff member that is not a Thunder reply
(store_forward) and queues THUNDER_FORWARD_TASK. The handler (process_intake) reads the whole
message and its attachments from Graph and acts on what it is about:
- a candidate's resume or profile: creates the candidate through the create_candidate queue
  (deduplicated by email or phone; an existing candidate is updated instead), then attaches the
  resume and saves the email as a note on the candidate;
- news about a candidate, a job or an employee: a note on that record;
- anything unclear, or a record the forwarder may not change: a task for the forwarder.
Nothing is dropped silently, and the (mailbox, Graph message id) key means no email is acted on twice.

Compensation: every write is in the row's own transaction; a failure rolls back and the queue
retries from the row's status (RECEIVED re-reads the email; CANDIDATE_QUEUED re-attaches, skipping
the note and resume already saved). Upstream: the forwarder (users), Graph Mail.Read on the mailbox.
Downstream: create_candidate (Thunder engagement of the new candidate), SharePoint for the resume.
"""
import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.mailbox_intake import MailboxIntakeMessage
from app.models.user import Users
from app.services.delivery_errors import DeliveryDeferred
from app.services.thunder_mail.forward_classifier import ForwardReading, read_forward

logger = logging.getLogger(__name__)

THUNDER_FORWARD_TASK = "thunder_process_forwarded_email"
CANDIDATE_SOURCE = "Email Forward"
NOTE_CATEGORY = "Forwarded Email"
ATTACH_DELAY_SECONDS = 30
CREATION_WAIT = timedelta(minutes=1)
MAX_NOTE_CHARS = 8000


def forward_task_id(intake_id: str, stage: str) -> str:
    return f"thunder_forward:{intake_id}:{stage}"


def forwarding_user(db: Session, sender: str) -> Optional[Users]:
    """The active staff member who sent (forwarded) the email, if any."""
    return db.query(Users).filter(func.lower(Users.UserEmail) == sender.lower(),
                                  Users.terminated_at.is_(None)).first()


def store_forward(db: Session, message: Dict, user: Users, mailbox_address: str,
                  received: datetime) -> Optional[str]:
    """Insert the intake row for one Graph message; None if an earlier run already stored it.
    Caller commits and queues THUNDER_FORWARD_TASK after the commit."""
    if db.query(MailboxIntakeMessage.id).filter_by(mailbox=mailbox_address,
                                                   graph_message_id=message["id"]).first():
        return None
    row = MailboxIntakeMessage(
        id=str(uuid.uuid4()), tenant_id=user.tenant_id, mailbox=mailbox_address,
        graph_message_id=message["id"], internet_message_id=message.get("internetMessageId"),
        from_address=user.UserEmail.lower(), forwarded_by_user_id=user.UserID,
        subject=(message.get("subject") or "")[:998], received_at=received, status="RECEIVED",
    )
    savepoint = db.begin_nested()
    try:
        db.add(row)
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()  # stored by an overlapping run
        return None
    return row.id


def queue_forward(intake_id: str, tenant_id: Optional[int], stage: str = "read", delay_seconds: int = 0) -> bool:
    from app.services.thunder_mail.cadence_service import enqueue_once

    return enqueue_once(THUNDER_FORWARD_TASK, forward_task_id(intake_id, stage),
                        {"intake_id": intake_id, "tenant_id": tenant_id}, tenant_id, delay_seconds=delay_seconds)


def link_created_candidate(db: Session, intake_id: str, candidate_id: str) -> None:
    """Called by the create_candidate handler, in its transaction, for a candidate queued from a
    forwarded email: the attach stage then finds the candidate."""
    row = db.query(MailboxIntakeMessage).filter_by(id=intake_id).first()
    if row is None:
        raise ValueError(f"Mailbox intake {intake_id} not found")
    row.candidate_id = candidate_id
    db.add(row)


# ---- processing -----------------------------------------------------------------------------

def process_intake(db: Session, intake_id: str, mailbox=None, *, llm_call: Optional[Callable] = None) -> Dict:
    row = db.query(MailboxIntakeMessage).filter_by(id=intake_id).first()
    if row is None:
        raise ValueError(f"Mailbox intake {intake_id} not found")
    if row.status in ("PROCESSED", "NEEDS_REVIEW"):
        return {"status": "already_processed", "intake_id": intake_id, "intake_status": row.status}
    forwarder = db.query(Users).filter(Users.UserID == row.forwarded_by_user_id).first()
    if forwarder is None:
        raise ValueError(f"Forwarding user {row.forwarded_by_user_id} of intake {intake_id} not found")
    if mailbox is None:
        from app.services.thunder_mail.graph_mailbox import GraphMailbox
        mailbox = GraphMailbox(row.mailbox)

    if row.status == "CANDIDATE_QUEUED":
        return _attach_to_candidate(db, row, forwarder, mailbox)

    message = mailbox.get_message(row.graph_message_id)
    attachments = mailbox.list_attachments(row.graph_message_id) if message.get("hasAttachments") else []
    reading = read_forward(db, row.tenant_id, row.subject or message.get("subject") or "",
                           (message.get("body") or {}).get("content") or "", attachments,
                           [forwarder.UserEmail, row.mailbox], llm_call=llm_call)
    row.kind, row.confidence, row.classifier_source = reading.kind, reading.confidence, reading.source
    row.extracted = _extracted(reading)
    logger.info(f"[ForwardIntake] read intake={row.id} kind={reading.kind} source={reading.source} "
                f"resume={'yes' if reading.resume else 'no'}")

    if reading.kind in ("NEW_CANDIDATE", "CANDIDATE_UPDATE"):
        return _candidate_email(db, row, forwarder, reading, mailbox)
    if reading.kind == "JOB_REQUIREMENT":
        return _job_email(db, row, forwarder, reading)
    if reading.kind == "EMPLOYEE_NOTE":
        return _employee_email(db, row, forwarder, reading)
    return _needs_review(db, row, forwarder, "It is not clear what this email is about.")


def _extracted(reading: ForwardReading) -> Dict:
    resume = reading.resume
    return {
        "summary": reading.summary, "forwarder_note": reading.forwarder_note,
        "original_sender_name": reading.original_sender_name,
        "original_sender_email": reading.original_sender_email,
        "candidate": reading.candidate, "job_reference": reading.job_reference,
        "employee_email": reading.employee_email, "emails": reading.emails, "phones": reading.phones,
        "resume": {"attachment_id": resume.attachment_id, "name": resume.name, "size": resume.size,
                   "text": resume.text} if resume else None,
        "unreadable_attachments": reading.unreadable_attachments,
    }


def _allowed(db: Session, user: Users, permission: str) -> bool:
    from app.core.authority import has_permission

    return has_permission(db, user, permission)


def _existing_candidate(db: Session, row: MailboxIntakeMessage, reading: ForwardReading) -> Optional[Candidate]:
    from app.services.candidate_service import find_duplicate_candidate

    details = reading.candidate
    emails = [e for e in [details.get("email")] + reading.emails if e]
    phones = [p for p in [details.get("phone")] + reading.phones if p]
    for email in dict.fromkeys(emails):
        hit = db.query(Candidate).filter(func.lower(Candidate.candidateEmail) == email.lower(),
                                         Candidate.tenant_id == row.tenant_id).first()
        if hit is not None:
            return hit
    for phone in dict.fromkeys(phones):
        hit, _ = find_duplicate_candidate(db, mobile=phone)
        if hit is not None and hit.tenant_id == row.tenant_id:
            return hit
    return None


def _candidate_email(db: Session, row, forwarder: Users, reading: ForwardReading, mailbox) -> Dict:
    existing = _existing_candidate(db, row, reading)
    if existing is not None:
        if not _allowed(db, forwarder, "candidates.edit"):
            return _needs_review(db, row, forwarder, "Your role cannot edit candidates, so this email about "
                                 f"{_name(existing)} was not added to their profile.", candidate_id=existing.candidateID)
        row.kind, row.candidate_id, row.status = "CANDIDATE_UPDATE", existing.candidateID, "CANDIDATE_QUEUED"
        db.commit()
        return _attach_to_candidate(db, row, forwarder, mailbox)
    if reading.kind == "CANDIDATE_UPDATE":
        return _needs_review(db, row, forwarder, "No candidate in the system matches the email addresses "
                             "or phone numbers in this email.")

    details = reading.candidate
    missing = [label for key, label in (("email", "email address"), ("first_name", "first name"),
                                        ("last_name", "last name")) if not details.get(key)]
    if missing:
        return _needs_review(db, row, forwarder, f"The candidate's {', '.join(missing)} could not be found "
                             "in the email or resume, so no candidate was created.")
    if not _allowed(db, forwarder, "candidates.create"):
        return _needs_review(db, row, forwarder, "Your role cannot create candidates, so no candidate was created.")

    from app.services.candidate_creation_wrapper import queue_candidate_creation

    years = details.get("total_experience_years")
    result = queue_candidate_creation(
        db=db, email=details["email"], first_name=details["first_name"], last_name=details["last_name"],
        tenant_id=row.tenant_id, source=CANDIDATE_SOURCE, mobile=details.get("phone"),
        created_by_user_id=forwarder.UserID, created_by_name=forwarder.UserName or forwarder.UserEmail,
        candidate_job_title=details.get("current_title"),
        candidate_current_location=details.get("current_location"),
        candidate_skills=details.get("skills") or None,
        candidate_experience=f"{years:g}" if isinstance(years, (int, float)) else None,
        mailbox_intake_id=row.id,
    )
    row.status, row.creation_message_id = "CANDIDATE_QUEUED", result["message_id"]
    db.commit()
    queue_forward(row.id, row.tenant_id, stage="attach", delay_seconds=ATTACH_DELAY_SECONDS)
    logger.info(f"[ForwardIntake] intake={row.id} queued candidate creation {result['message_id']}")
    return {"status": "candidate_queued", "intake_id": row.id, "creation_message_id": result["message_id"]}


def _attach_to_candidate(db: Session, row, forwarder: Users, mailbox) -> Dict:
    if row.candidate_id is None:
        from app.models.channel_queue import ChannelQueueItem
        from app.services.message_queue_service import IN_FLIGHT_STATUSES

        creation = db.query(ChannelQueueItem).filter(ChannelQueueItem.id == row.creation_message_id).first()
        if creation is not None and creation.status in IN_FLIGHT_STATUSES + ("RETRY",):
            raise DeliveryDeferred(f"Waiting for candidate creation {row.creation_message_id}",
                                   retry_at=datetime.utcnow() + CREATION_WAIT)
        # The queue folds an identical in-flight request (same email, same source) into one
        # message that does not carry this intake: the candidate it created is found by email
        email = ((row.extracted or {}).get("candidate") or {}).get("email")
        created = db.query(Candidate).filter(func.lower(Candidate.candidateEmail) == email,
                                             Candidate.tenant_id == row.tenant_id).first() \
            if email and creation is not None and creation.status == "COMPLETED" else None
        if created is None:
            reason = (creation.error if creation is not None else None) or "the creation message is missing"
            return _needs_review(db, row, forwarder, f"Creating the candidate failed: {reason}")
        row.candidate_id = created.candidateID

    candidate = db.query(Candidate).filter(Candidate.candidateID == row.candidate_id).first()
    if candidate is None:
        raise ValueError(f"Candidate {row.candidate_id} of intake {row.id} not found")
    extracted = row.extracted or {}
    resume = extracted.get("resume")

    if row.note_id is None:
        if row.kind == "CANDIDATE_UPDATE":
            _fill_blanks(candidate, extracted.get("candidate") or {})
        if resume and resume.get("text"):
            _save_parsed_resume(db, candidate, resume["text"], extracted.get("candidate") or {})
        row.note_id = _candidate_note(db, row, forwarder, candidate, extracted)
        db.commit()

    if resume and row.document_id is None:
        problem = _attach_resume(db, row, forwarder, candidate, resume, mailbox)
        if problem:
            return _needs_review(db, row, forwarder, problem, candidate_id=candidate.candidateID)

    row.status, row.processed_at = "PROCESSED", datetime.utcnow()
    db.commit()
    logger.info(f"[ForwardIntake] intake={row.id} processed: candidate={candidate.candidateID} "
                f"note={row.note_id} resume_document={row.document_id}")
    return {"status": "processed", "intake_id": row.id, "candidate_id": candidate.candidateID,
            "note_id": row.note_id, "document_id": row.document_id}


def _fill_blanks(candidate: Candidate, details: Dict) -> None:
    """An existing candidate keeps what recruiters entered; only empty fields are filled."""
    for column, key in (("candidateMobile", "phone"), ("candidateJobTitle", "current_title"),
                        ("candidateCurrentLocation", "current_location")):
        if not getattr(candidate, column) and details.get(key):
            setattr(candidate, column, details[key])
    if not candidate.candidateSkills and details.get("skills"):
        candidate.candidateSkills = ", ".join(details["skills"])


def _save_parsed_resume(db: Session, candidate: Candidate, text: str, details: Dict) -> None:
    from app.models.candidate_resume_parsed import CandidateResumeParsed
    from app.services.resume_parser_slm import ResumeSLM

    parsed = ResumeSLM.parse_resume(text)
    row = db.query(CandidateResumeParsed).filter_by(candidate_id=candidate.candidateID).first()
    if row is None:
        row = CandidateResumeParsed(candidate_id=candidate.candidateID, tenant_id=str(candidate.tenant_id))
        db.add(row)
    years = details.get("total_experience_years")
    row.raw_text, row.full_name, row.email, row.phone = text, parsed["full_name"], parsed["email"], parsed["phone"]
    row.current_title, row.current_employer = parsed["current_title"], parsed["current_employer"]
    row.work_history, row.education, row.skills = parsed["work_history"], parsed["education"], parsed["skills"]
    row.certifications, row.languages = parsed["certifications"], parsed["languages"]
    row.total_experience_years = years if isinstance(years, (int, float)) else None
    row.total_experience_months = round(years * 12) if isinstance(years, (int, float)) else None
    row.parsed_at = datetime.utcnow()
    from app.services.resume_completeness_service import calculate_resume_completeness

    db.flush()
    score = calculate_resume_completeness(row)
    row.resume_completeness_score, row.score_calculated_at = score, datetime.utcnow()
    candidate.resume_completeness_score = score


def _note_text(row, forwarder: Users, extracted: Dict) -> str:
    lines = [f"Forwarded by {forwarder.UserName or forwarder.UserEmail} to the HRMS mailbox"
             f"{' on ' + row.received_at.strftime('%Y-%m-%d %H:%M UTC') if row.received_at else ''}: "
             f"\"{row.subject or '(no subject)'}\""]
    if extracted.get("forwarder_note"):
        lines.append(f"Their note: {extracted['forwarder_note']}")
    if extracted.get("original_sender_email"):
        lines.append(f"Original sender: {extracted.get('original_sender_name') or ''} "
                     f"<{extracted['original_sender_email']}>".replace("  ", " "))
    if extracted.get("summary"):
        lines.append(f"Summary: {extracted['summary']}")
    if extracted.get("resume"):
        lines.append(f"Resume: {extracted['resume']['name']}")
    for problem in extracted.get("unreadable_attachments") or []:
        lines.append(f"Not read: {problem}")
    return "\n".join(lines)[:MAX_NOTE_CHARS]


def _candidate_note(db: Session, row, forwarder: Users, candidate: Candidate, extracted: Dict) -> int:
    from app.models.internal_note import InternalNote
    from app.services.activity_timeline_service import write_timeline_entry

    note = InternalNote(candidate_id=candidate.candidateID, content=_note_text(row, forwarder, extracted),
                        category=NOTE_CATEGORY, created_by_id=forwarder.UserID,
                        created_by_name=forwarder.UserName or forwarder.UserEmail)
    db.add(note)
    write_timeline_entry(db, entity_type="candidate", entity_id=candidate.candidateID, action="email_forwarded",
                         tenant_id=candidate.tenant_id, actor_id=forwarder.UserID, actor_type="USER",
                         description=f"Email forwarded to the HRMS mailbox: {row.subject or '(no subject)'}")
    db.flush()
    return note.id


def _attach_resume(db: Session, row, forwarder: Users, candidate: Candidate, resume: Dict, mailbox) -> Optional[str]:
    """Upload the resume like the HR resume upload does (SharePoint + candidate_documents). Returns
    why it could not be attached when storage is not set up; raises RuntimeError (retried) when
    Graph or SharePoint fails."""
    from fastapi import HTTPException

    from app.core.graph_auth import GraphServiceAuth, get_graph_token
    from app.services import document_service
    from app.services.virus_scan_service import scan_document_content

    if not (GraphServiceAuth.is_configured() and document_service.SHAREPOINT_SITE_ID
            and document_service.SHAREPOINT_DRIVE_ID):
        return (f"The resume {resume['name']} could not be attached: document storage (SharePoint) is not "
                "configured. Download it from the email and upload it on the candidate's Documents tab.")
    if mailbox is None:
        from app.services.thunder_mail.graph_mailbox import GraphMailbox
        mailbox = GraphMailbox(row.mailbox)
    attachment = mailbox.get_attachment(row.graph_message_id, resume["attachment_id"])
    content = base64.b64decode(attachment["contentBytes"])
    service = document_service.DocumentService(db)
    filename = service.generate_unique_filename(resume["name"], candidate.candidateID, "resume")
    try:
        stored = service.upload_to_sharepoint(get_graph_token(), candidate.candidateID, "resume", content, filename)
    except HTTPException as exc:
        raise RuntimeError(f"Resume upload for intake {row.id} failed: {exc.detail}") from exc
    extension = "." + resume["name"].rsplit(".", 1)[-1].lower() if "." in resume["name"] else ""
    document = service.save_document_metadata(
        candidate_id=candidate.candidateID, document_type="resume", original_filename=resume["name"],
        unique_filename=filename, file_size=len(content), file_extension=extension, sharepoint_data=stored,
        uploaded_by=forwarder.UserID)
    scan_document_content(document, content)
    from app.services.candidate_activity_service import log_resume_uploaded

    log_resume_uploaded(db, candidate.candidateID, resume["name"], len(content) / (1024 * 1024),
                        uploaded_by_user_id=forwarder.UserID, uploaded_by_name=forwarder.UserName)
    row.document_id = document.id
    db.commit()
    return None


def _timeline_note(db: Session, row, forwarder: Users, entity_type: str, entity_id: str) -> Dict:
    from app.services.activity_timeline_service import write_timeline_entry

    entry = write_timeline_entry(db, entity_type=entity_type, entity_id=entity_id, action="email_forwarded",
                                 tenant_id=row.tenant_id, actor_id=forwarder.UserID, actor_type="USER",
                                 description=_note_text(row, forwarder, row.extracted or {}))
    db.flush()
    row.note_id, row.status, row.processed_at = entry.id, "PROCESSED", datetime.utcnow()
    db.commit()
    logger.info(f"[ForwardIntake] intake={row.id} processed: note on {entity_type} {entity_id}")
    return {"status": "processed", "intake_id": row.id, entity_type + "_id": entity_id, "note_id": entry.id}


def _job_email(db: Session, row, forwarder: Users, reading: ForwardReading) -> Dict:
    from app.core import data_scope
    from app.models.user import Jobs

    reference = (reading.job_reference or "").strip()
    jobs = db.query(Jobs).filter(Jobs.tenant_id == row.tenant_id, Jobs.is_deleted.is_(False))
    matches = jobs.filter(or_(Jobs.jobID == reference, func.lower(Jobs.jobTitle) == reference.lower())).all() \
        if reference else []
    if len(matches) != 1:
        return _needs_review(db, row, forwarder, "This looks like a job requirement, but it matches "
                             f"{'no' if not matches else len(matches)} existing job"
                             f"{'s' if len(matches) > 1 else ''}"
                             f"{' (' + reference + ')' if reference else ''}. Create the job or add it to the right one.")
    job = matches[0]
    row.job_id = job.jobID
    if not (_allowed(db, forwarder, "activity-feed.create") and data_scope.can_see_bu(db, forwarder, job.business_unit_id)):
        return _needs_review(db, row, forwarder, f"Your role cannot add notes to the job {job.jobTitle}.")
    return _timeline_note(db, row, forwarder, "job", job.jobID)


def _employee_email(db: Session, row, forwarder: Users, reading: ForwardReading) -> Dict:
    from app.core import data_scope
    from app.models.employee import Employee

    emails = [e for e in [reading.employee_email, reading.original_sender_email] + reading.emails if e]
    employee = None
    for email in dict.fromkeys(emails):
        employee = db.query(Employee).filter(Employee.tenant_id == row.tenant_id, or_(
            func.lower(Employee.email) == email, func.lower(Employee.personal_email) == email)).first()
        if employee is not None:
            break
    if employee is None:
        return _needs_review(db, row, forwarder, "This email is about an employee, but no employee in the "
                             "system matches the email addresses in it.")
    row.employee_id = employee.id
    if not (_allowed(db, forwarder, "activity-feed.create") and data_scope.can_see_bu(db, forwarder, employee.bu_id)):
        return _needs_review(db, row, forwarder, f"Your role cannot add notes to {employee.first_name} "
                             f"{employee.last_name}'s record.")
    return _timeline_note(db, row, forwarder, "employee", employee.id)


def _name(candidate: Candidate) -> str:
    return " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])) or candidate.candidateID


def _needs_review(db: Session, row, forwarder: Users, reason: str, candidate_id: Optional[str] = None) -> Dict:
    """One task for the person who forwarded the email (they know what it was for)."""
    from app.services.task_service import create_task

    extracted = row.extracted or {}
    details = extracted.get("candidate") or {}
    description = "\n".join(filter(None, [
        reason,
        f"Email: \"{row.subject or '(no subject)'}\", forwarded"
        f"{' on ' + row.received_at.strftime('%Y-%m-%d %H:%M UTC') if row.received_at else ''} "
        f"to {row.mailbox} (it is still in that mailbox).",
        f"Read as: {row.kind or 'unknown'}" + (f" - {extracted['summary']}" if extracted.get("summary") else ""),
        f"Original sender: {extracted['original_sender_email']}" if extracted.get("original_sender_email") else None,
        "Details found: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in details.items()
                                       if v and k in ("first_name", "last_name", "email", "phone"))
        if any(details.get(k) for k in ("first_name", "last_name", "email", "phone")) else None,
        f"Resume attached to the email: {extracted['resume']['name']}" if extracted.get("resume") else None,
    ]))
    task = create_task(db, title=f"Forwarded email needs you: {row.subject or '(no subject)'}"[:300],
                       description=description, priority="MEDIUM", tenant_id=row.tenant_id,
                       assigned_to_user_id=forwarder.UserID, created_by_user_id=forwarder.UserID,
                       due_date=datetime.utcnow(), category="MAILBOX_INTAKE")
    if candidate_id:
        task.candidate_id = row.candidate_id = candidate_id
    row.task_id, row.review_reason = task.id, reason
    row.status, row.processed_at = "NEEDS_REVIEW", datetime.utcnow()
    db.commit()
    logger.info(f"[ForwardIntake] intake={row.id} needs review (task {task.id}): {reason}")
    return {"status": "needs_review", "intake_id": row.id, "task_id": task.id, "reason": reason}
