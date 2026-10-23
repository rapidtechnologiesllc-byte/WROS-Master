"""Client timesheet approval (CEO 2026-10-23, gap 3): for a client with
Client.requires_client_timesheet_approval, a week approved internally (timesheet_approval_service)
also needs the client's own approver before it is invoiced.

internal approval -> on_internal_approval: the timesheet stays APPROVED and becomes CLIENT_PENDING;
                     a ClientTimesheetApproval request is opened for the placement's client approver
                     (EmployeeAllocation.timesheet_approver_email). After commit, queue_email() queues
                     the email; its handler issues a single-use link that expires after
                     CLIENT_TIMESHEET_APPROVAL_LINK_TTL_HOURS (only the token's SHA-256 is stored).
                     No approver email on the placement: a task for the internal approver instead.
link approve       -> CLIENT_APPROVED, client_approver_email and client_approved_at recorded.
link reject        -> a reason is required; the timesheet goes back to the employee through the same
                     resubmit task the internal rejection uses (timesheet_approval_service.
                     client_reject), CLIENT_REJECTED. Resubmitted and approved again, it asks the
                     client again with a new link (the old one is superseded).
evidence           -> an internal approver uploads the client's VMS-approved timesheet: CLIENT_APPROVED
                     with who, when and the file (method EVIDENCE).
resend             -> a new request and link; the open one is superseded.

The public page sees only this week's employee name, client, dates and hours: no rates, notes or
other records. Invoicing refuses weeks that are not CLIENT_APPROVED (not_client_approved, called by
invoice_service.generate_invoice)."""
import hashlib
import html
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client, ClientContact
from app.models.client_timesheet_approval import ClientTimesheetApproval
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users

logger = logging.getLogger(__name__)

CLIENT_PENDING, CLIENT_APPROVED, CLIENT_REJECTED = "CLIENT_PENDING", "CLIENT_APPROVED", "CLIENT_REJECTED"
EMAIL_TASK = "send_client_timesheet_approval"
PUBLIC_PATH = "/client-timesheet-approval"
APPROVAL_PATH = "/timesheet-approvals/{timesheet_id}"
EVIDENCE_TYPES = {
    "application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
    "text/csv": ".csv", "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_REASON_LENGTH = 2000


class ClientApprovalError(Exception):
    """The request cannot be done in the timesheet's current state (shown to the user)."""


class ClientLinkInvalid(Exception):
    """The link is unknown, used, superseded or expired."""


class NotAllowed(Exception):
    pass


# ---------------------------------------------------------------------------- lookups

def _allocation(db: Session, timesheet: Timesheet) -> Optional[EmployeeAllocation]:
    return db.get(EmployeeAllocation, timesheet.allocation_id) if timesheet.allocation_id else None


def client_of(db: Session, timesheet: Timesheet) -> Optional[Client]:
    allocation = _allocation(db, timesheet)
    return db.get(Client, allocation.client_id) if allocation is not None else None


def requires_client_approval(db: Session, timesheet: Timesheet) -> bool:
    client = client_of(db, timesheet)
    return bool(client is not None and client.requires_client_timesheet_approval)


def not_client_approved(db: Session, timesheets: List[Timesheet]) -> List[Timesheet]:
    """The weeks invoicing must wait for: the client requires its own approval and has not given it."""
    return [ts for ts in timesheets
            if ts.client_approval_status != CLIENT_APPROVED and requires_client_approval(db, ts)]


def _name(employee: Optional[Employee]) -> str:
    return f"{employee.first_name} {employee.last_name or ''}".strip() if employee else "(unknown employee)"


def describe(db: Session, timesheets: List[Timesheet]) -> str:
    parts = []
    for ts in timesheets:
        state = (ts.client_approval_status or "not requested").replace("CLIENT_", "").lower().replace("_", " ")
        parts.append(f"{_name(db.get(Employee, ts.employee_id))} week of {ts.week_starting_date} "
                     f"({state}, timesheet {ts.id})")
    return "; ".join(parts)


def _open_requests(db: Session, timesheet: Timesheet) -> List[ClientTimesheetApproval]:
    return db.query(ClientTimesheetApproval).filter(ClientTimesheetApproval.timesheet_id == timesheet.id,
                                                    ClientTimesheetApproval.decision == "PENDING").all()


def latest_request(db: Session, timesheet: Timesheet) -> Optional[ClientTimesheetApproval]:
    return db.query(ClientTimesheetApproval).filter(ClientTimesheetApproval.timesheet_id == timesheet.id) \
        .order_by(ClientTimesheetApproval.id.desc()).first()


def normalize_email(email: Optional[str]) -> Optional[str]:
    email = (email or "").strip().lower()
    return email or None


def validate_approver_email(db: Session, client: Client, email: Optional[str]) -> Optional[str]:
    """A client timesheet approver for a placement: a valid address and, when the client has active
    TIMESHEET_APPROVER contacts, one of them (so a typo cannot send approvals to a stranger)."""
    email = normalize_email(email)
    if email is None:
        return None
    if not EMAIL_RE.match(email):
        raise ClientApprovalError(f"'{email}' is not a valid email address.")
    approvers = [normalize_email(c.email) for c in db.query(ClientContact).filter(
        ClientContact.client_id == client.id, ClientContact.role_type == "TIMESHEET_APPROVER",
        ClientContact.is_active.is_(True)).all() if c.email]
    if approvers and email not in approvers:
        raise ClientApprovalError(
            f"{email} is not one of {client.company_name}'s timesheet approver contacts ({', '.join(sorted(approvers))}). "
            "Pick one of them, or add this person as a TIMESHEET_APPROVER contact on the client first.")
    return email


# ---------------------------------------------------------------------------- opening a request

def _close_task(db: Session, task_id: Optional[int]) -> None:
    from app.models.task import Task

    task = db.get(Task, task_id) if task_id else None
    if task is not None and task.status not in ("COMPLETED", "CANCELLED"):
        task.status, task.completed_at = "COMPLETED", datetime.utcnow()


def _supersede_open(db: Session, timesheet: Timesheet, now: datetime) -> None:
    for old in _open_requests(db, timesheet):
        old.decision, old.used_at = "SUPERSEDED", old.used_at or now
        _close_task(db, old.task_id)


def _internal_approver_id(db: Session, timesheet: Timesheet, fallback: Optional[str]) -> Optional[str]:
    from app.services.timesheet_approval_service import latest_review

    review = latest_review(db, timesheet)
    return review.approver_user_id if review is not None else fallback


def open_request(db: Session, timesheet: Timesheet, *, requested_by: Optional[str],
                 raise_task: bool = True) -> ClientTimesheetApproval:
    """A new client approval request for this approved week (any open one is superseded). With no
    approver email on the placement, the internal approver gets a task to upload the client's
    approved timesheet instead. The caller commits, then calls queue_email()."""
    from app.services.task_service import create_task

    client = client_of(db, timesheet)
    if client is None:
        raise ClientApprovalError("This timesheet is not for a client placement.")
    now = datetime.utcnow()
    _supersede_open(db, timesheet, now)
    email = normalize_email((_allocation(db, timesheet)).timesheet_approver_email)
    timesheet.client_approval_status, timesheet.client_approver_email = CLIENT_PENDING, email
    timesheet.client_approved_at = None
    request = ClientTimesheetApproval(tenant_id=timesheet.tenant_id, timesheet_id=timesheet.id, client_id=client.id,
                                      approver_email=email, method="LINK" if email else None,
                                      requested_by_user_id=requested_by)
    db.add(request)
    db.flush()
    if email is None and raise_task:
        employee = db.get(Employee, timesheet.employee_id)
        assignee = _internal_approver_id(db, timesheet, requested_by)
        task = create_task(
            db, title=f"Client approval needed: {_name(employee)} week of {timesheet.week_starting_date} "
                      f"({client.company_name})",
            description=(f"{client.company_name} approves its own timesheets before they are invoiced, and "
                         f"{_name(employee)}'s placement has no client timesheet approver email. Upload the "
                         "client's approved timesheet (e.g. the VMS export) on the approval page, or set the "
                         "approver on the placement (Clients > Billing setup) and send the request."),
            priority="HIGH", tenant_id=timesheet.tenant_id, assigned_to_user_id=assignee,
            created_by_user_id=requested_by, category="TIMESHEET_APPROVAL",
            due_date=now + timedelta(days=3), link=APPROVAL_PATH.format(timesheet_id=timesheet.id))
        request.task_id = task.id
    logger.info(f"[ClientTimesheetApproval] {timesheet.id} -> {CLIENT_PENDING} request {request.id} "
                f"approver={email or 'none (task)'}")
    return request


def on_internal_approval(db: Session, timesheet: Timesheet, approved_by: Optional[str]) -> Optional[ClientTimesheetApproval]:
    """Called by timesheet_service.approve_timesheet on every internal approval."""
    if not requires_client_approval(db, timesheet):
        return None
    return open_request(db, timesheet, requested_by=approved_by)


def queue_email(db: Session, timesheet: Timesheet) -> bool:
    """After commit: queue the email of the open request (once per request). Raises when it cannot
    be queued: the client must hear about it, and the request can be sent again from the page."""
    from app.services.thunder_mail.cadence_service import enqueue_once

    request = next((r for r in _open_requests(db, timesheet) if r.approver_email and r.emailed_at is None), None)
    if request is None:
        return False
    return enqueue_once(EMAIL_TASK, f"client-ts-approval-{request.id}", {"request_id": request.id},
                        timesheet.tenant_id)


# ---------------------------------------------------------------------------- the emailed link

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_link(db: Session, request: ClientTimesheetApproval, now: Optional[datetime] = None) -> str:
    """A fresh unguessable token for this request (plaintext returned once, for the email)."""
    now = now or datetime.utcnow()
    plaintext = secrets.token_urlsafe(32)
    request.token_hash = _hash(plaintext)
    request.expires_at = now + timedelta(hours=settings.CLIENT_TIMESHEET_APPROVAL_LINK_TTL_HOURS)
    db.flush()
    return plaintext


def link_for(plaintext: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{PUBLIC_PATH}?token={plaintext}"


def _issuer_name(db: Session, client: Client, tenant_id: Optional[int]) -> str:
    from app.models.location import Location
    from app.models.tenant import Tenant

    company = db.get(Location, client.contracting_company_id) if client.contracting_company_id else None
    if company is not None:
        return company.name
    tenant = db.get(Tenant, tenant_id) if tenant_id else None
    return tenant.name if tenant else "us"


def _week(db: Session, timesheet: Timesheet) -> Dict:
    entries = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id) \
        .order_by(TimesheetEntry.entry_date).all()
    return {
        "week_starting_date": timesheet.week_starting_date.isoformat(),
        "week_ending_date": (timesheet.week_starting_date + timedelta(days=6)).isoformat(),
        "entries": [{"entry_date": e.entry_date.isoformat(), "hours": float(e.hours), "entry_type": e.entry_type}
                    for e in entries],
        "total_hours": float(timesheet.total_hours or 0),
        "billable_hours": float(timesheet.billable_hours or 0),
    }


def render_email(db: Session, request: ClientTimesheetApproval, link: str) -> Dict[str, str]:
    timesheet = db.get(Timesheet, request.timesheet_id)
    client = db.get(Client, request.client_id)
    employee = db.get(Employee, timesheet.employee_id)
    issuer = _issuer_name(db, client, timesheet.tenant_id)
    week = _week(db, timesheet)
    rows = "".join(f"<tr><td>{e['entry_date']}</td><td style='text-align:right'>{e['hours']:g}</td>"
                   f"<td>{html.escape(e['entry_type'].replace('_', ' ').lower())}</td></tr>" for e in week["entries"])
    days = max(1, settings.CLIENT_TIMESHEET_APPROVAL_LINK_TTL_HOURS // 24)
    body = (
        f"<p>Hello,</p><p>{html.escape(_name(employee))} worked <b>{week['total_hours']:g} hours</b> for "
        f"{html.escape(client.company_name)} in the week of {week['week_starting_date']} to "
        f"{week['week_ending_date']}. Please approve the hours, or reject them with a reason.</p>"
        "<table cellpadding='6' style='border-collapse:collapse;border:1px solid #ccc'>"
        f"<tr><th align='left'>Day</th><th>Hours</th><th align='left'>Type</th></tr>{rows}</table>"
        f"<p><a href=\"{html.escape(link, quote=True)}\">Review and approve the timesheet</a></p>"
        f"<p>The link works once and expires in {days} day(s).</p>"
        f"<p>Regards,<br>{html.escape(issuer)}</p>"
    )
    return {"subject": f"Timesheet approval: {_name(employee)}, week of {week['week_starting_date']}",
            "html": body}


def _request_for_token(db: Session, plaintext: str, now: datetime, *, lock: bool) -> ClientTimesheetApproval:
    if not plaintext or len(plaintext) > 200:
        raise ClientLinkInvalid("This approval link is not valid.")
    query = db.query(ClientTimesheetApproval).filter(ClientTimesheetApproval.token_hash == _hash(plaintext))
    request = (query.with_for_update() if lock else query).first()
    if request is None:
        raise ClientLinkInvalid("This approval link is not valid.")
    if request.decision != "PENDING" or request.used_at is not None:
        raise ClientLinkInvalid("This approval link was already used or replaced by a newer one.")
    if request.expires_at is None or request.expires_at < now:
        raise ClientLinkInvalid("This approval link has expired. Ask us to send a new one.")
    timesheet = db.get(Timesheet, request.timesheet_id)
    if timesheet is None or timesheet.status != "APPROVED" or timesheet.client_approval_status != CLIENT_PENDING:
        raise ClientLinkInvalid("This timesheet is no longer waiting for your approval.")
    return request


def public_view(db: Session, plaintext: str, now: Optional[datetime] = None) -> Dict:
    """Only what the client approver needs to decide this one week."""
    now = now or datetime.utcnow()
    request = _request_for_token(db, plaintext, now, lock=False)
    timesheet = db.get(Timesheet, request.timesheet_id)
    client = db.get(Client, request.client_id)
    return {"employee_name": _name(db.get(Employee, timesheet.employee_id)), "client_name": client.company_name,
            "issuer_name": _issuer_name(db, client, timesheet.tenant_id),
            "expires_at": request.expires_at.isoformat(), **_week(db, timesheet)}


def _tell_internal_approver(db: Session, timesheet: Timesheet, text: str) -> None:
    from app.services.flash_conversation_service import post_event

    approver_id = _internal_approver_id(db, timesheet, None)
    approver = db.get(Users, approver_id) if approver_id else None
    if approver is not None:
        post_event(db, approver.UserID, approver.tenant_id, text,
                   {"kind": "timesheet_approval", "link": APPROVAL_PATH.format(timesheet_id=timesheet.id)})


def approve_by_link(db: Session, plaintext: str, *, ip: Optional[str] = None,
                    now: Optional[datetime] = None) -> ClientTimesheetApproval:
    """The client approved: the week can be invoiced. The caller commits."""
    now = now or datetime.utcnow()
    request = _request_for_token(db, plaintext, now, lock=True)
    timesheet = db.query(Timesheet).filter(Timesheet.id == request.timesheet_id).with_for_update().one()
    request.decision, request.method, request.used_at, request.decided_at = "APPROVED", "LINK", now, now
    request.decided_ip = (ip or "")[:64] or None
    timesheet.client_approval_status, timesheet.client_approved_at = CLIENT_APPROVED, now
    timesheet.client_approver_email = request.approver_email
    employee = db.get(Employee, timesheet.employee_id)
    _tell_internal_approver(db, timesheet, f"The client ({request.approver_email}) approved {_name(employee)}'s "
                                           f"timesheet for the week of {timesheet.week_starting_date}.")
    logger.info(f"[ClientTimesheetApproval] {timesheet.id} {CLIENT_APPROVED} by link request {request.id}")
    return request


def reject_by_link(db: Session, plaintext: str, reason: str, *, ip: Optional[str] = None,
                   now: Optional[datetime] = None):
    """The client rejected with a reason: back to the employee through the resubmit task. Returns the
    TimesheetReview for timesheet_approval_service.send_notices (after the caller commits)."""
    from app.services.timesheet_approval_service import client_reject

    now = now or datetime.utcnow()
    reason = (reason or "").strip()
    if not reason:
        raise ClientApprovalError("Please give the reason for rejecting the timesheet.")
    if len(reason) > MAX_REASON_LENGTH:
        raise ClientApprovalError(f"Please keep the reason under {MAX_REASON_LENGTH} characters.")
    request = _request_for_token(db, plaintext, now, lock=True)
    timesheet = db.query(Timesheet).filter(Timesheet.id == request.timesheet_id).with_for_update().one()
    request.decision, request.method, request.used_at, request.decided_at = "REJECTED", "LINK", now, now
    request.reason, request.decided_ip = reason, (ip or "")[:64] or None
    timesheet.client_approval_status = CLIENT_REJECTED
    review = client_reject(db, timesheet, client_email=request.approver_email, reason=reason)
    employee = db.get(Employee, timesheet.employee_id)
    _tell_internal_approver(db, timesheet, f"The client ({request.approver_email}) rejected {_name(employee)}'s "
                                           f"timesheet for the week of {timesheet.week_starting_date}: {reason}")
    logger.info(f"[ClientTimesheetApproval] {timesheet.id} {CLIENT_REJECTED} by link request {request.id}")
    return review


# ---------------------------------------------------------------------------- internal side

def may_act(db: Session, timesheet: Timesheet, user: Users) -> bool:
    """The routed internal approver, or someone with timesheet edit rights on its business unit."""
    from app.core import authority
    from app.core.data_scope import timesheet_filter
    from app.services.timesheet_approval_service import latest_review, may_decide

    review = latest_review(db, timesheet)
    if review is not None:
        return may_decide(db, review, user)
    if not authority.has_permission(db, user, "timesheets.edit"):
        return False
    return db.query(Timesheet.id).filter(Timesheet.id == timesheet.id, Timesheet.tenant_id == user.tenant_id,
                                         timesheet_filter(db, user)).first() is not None


def _ensure_actionable(db: Session, timesheet: Timesheet, user: Users) -> Client:
    if not may_act(db, timesheet, user):
        raise NotAllowed("Only the timesheet's approver, or someone with timesheet edit rights on its business "
                         "unit, can record the client's approval.")
    client = client_of(db, timesheet)
    if client is None or not client.requires_client_timesheet_approval:
        raise ClientApprovalError("This client does not require client timesheet approval.")
    if timesheet.status != "APPROVED":
        raise ClientApprovalError("Approve the timesheet internally first; the client is asked after that.")
    if timesheet.client_approval_status == CLIENT_APPROVED:
        raise ClientApprovalError("The client already approved this timesheet.")
    return client


def request_again(db: Session, timesheet: Timesheet, user: Users) -> ClientTimesheetApproval:
    """Send (or re-send) the approval email with a new link; the open link stops working."""
    _ensure_actionable(db, timesheet, user)
    if not normalize_email(_allocation(db, timesheet).timesheet_approver_email):
        raise ClientApprovalError("The placement has no client timesheet approver email. Set it on the client's "
                                  "Billing setup tab, or upload the client's approved timesheet instead.")
    return open_request(db, timesheet, requested_by=user.UserID)


def evidence_dir(tenant_id) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "client-timesheet-approvals", str(tenant_id))
    os.makedirs(path, exist_ok=True)
    return path


def record_evidence(db: Session, timesheet: Timesheet, user: Users, *, filename: str, content_type: str,
                    data: bytes, note: Optional[str] = None) -> ClientTimesheetApproval:
    """The client approved in its own system (VMS): store the approved export and mark the week
    client-approved, recording who uploaded it and when. The caller commits."""
    _ensure_actionable(db, timesheet, user)
    if content_type not in EVIDENCE_TYPES:
        raise ClientApprovalError("Upload the client's approved timesheet as a PDF, image, CSV or Excel file "
                                  f"(got {content_type or 'unknown'}).")
    if not data:
        raise ClientApprovalError("The file is empty.")
    if len(data) > settings.CLIENT_TIMESHEET_EVIDENCE_MAX_BYTES:
        raise ClientApprovalError(f"The file is larger than {settings.CLIENT_TIMESHEET_EVIDENCE_MAX_BYTES // (1024 * 1024)} MB.")
    now = datetime.utcnow()
    request = next(iter(_open_requests(db, timesheet)), None)
    if request is None:  # approved before the client flag was on: record it on a request of its own
        request = open_request(db, timesheet, requested_by=user.UserID, raise_task=False)
    for other in _open_requests(db, timesheet):
        if other.id != request.id:
            other.decision, other.used_at = "SUPERSEDED", now
            _close_task(db, other.task_id)
    path = os.path.join(evidence_dir(timesheet.tenant_id), f"{request.id}{EVIDENCE_TYPES[content_type]}")
    with open(path, "wb") as handle:
        handle.write(data)
    request.decision, request.method, request.decided_at, request.used_at = "APPROVED", "EVIDENCE", now, now
    request.recorded_by_user_id, request.reason = user.UserID, (note or "").strip() or None
    request.evidence_path, request.evidence_content_type = path, content_type
    request.evidence_filename = os.path.basename(filename or "")[:512] or f"evidence{EVIDENCE_TYPES[content_type]}"
    _close_task(db, request.task_id)
    timesheet.client_approval_status, timesheet.client_approved_at = CLIENT_APPROVED, now
    timesheet.client_approver_email = request.approver_email or timesheet.client_approver_email
    logger.info(f"[ClientTimesheetApproval] {timesheet.id} {CLIENT_APPROVED} by evidence from {user.UserID} "
                f"request {request.id}")
    return request


def status_view(db: Session, timesheet: Timesheet) -> Optional[Dict]:
    """What the internal approval page shows about the client's approval (None when not required
    and never asked)."""
    required = requires_client_approval(db, timesheet)
    request = latest_request(db, timesheet)
    if not required and request is None:
        return None
    recorder = db.get(Users, request.recorded_by_user_id) if request is not None and request.recorded_by_user_id else None
    allocation = _allocation(db, timesheet)
    return {
        "required": required,
        "status": timesheet.client_approval_status,
        "approver_email": timesheet.client_approver_email,
        "placement_approver_email": allocation.timesheet_approver_email if allocation is not None else None,
        "approved_at": timesheet.client_approved_at.isoformat() if timesheet.client_approved_at else None,
        "request": None if request is None else {
            "id": request.id, "decision": request.decision, "method": request.method,
            "approver_email": request.approver_email,
            "emailed_at": request.emailed_at.isoformat() if request.emailed_at else None,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "decided_at": request.decided_at.isoformat() if request.decided_at else None,
            "reason": request.reason, "evidence_filename": request.evidence_filename,
            "recorded_by": (recorder.UserName or recorder.UserEmail) if recorder else None,
        },
        "can_request": bool(required and timesheet.status == "APPROVED"
                            and timesheet.client_approval_status != CLIENT_APPROVED),
    }


def evidence_for(db: Session, timesheet: Timesheet) -> Optional[ClientTimesheetApproval]:
    return db.query(ClientTimesheetApproval).filter(ClientTimesheetApproval.timesheet_id == timesheet.id,
                                                    ClientTimesheetApproval.method == "EVIDENCE",
                                                    ClientTimesheetApproval.evidence_path.isnot(None)) \
        .order_by(ClientTimesheetApproval.id.desc()).first()
