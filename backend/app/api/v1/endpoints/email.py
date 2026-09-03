"""
HRMS Email Service Endpoints
Provides production-ready mail & interview scheduling APIs backed by
Microsoft Graph via helpdesk_hrms@blitzenx.com.
"""
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, get_current_user, require_permission
from app.core.logging import logger
from app.models import Candidate, Interview, InterviewPanel, PanelMember, Users
from app.services.email_service import EmailService

router = APIRouter(prefix="/email", tags=["Email Service"])



# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Request / Response schemas
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
logger = logging.getLogger(__name__)

class SendMailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body_content: str
    is_html: bool = True
    cc_emails: Optional[List[EmailStr]] = None


class SendNotificationRequest(BaseModel):
    to_email: EmailStr
    heading: str
    message: str
    cc_emails: Optional[List[EmailStr]] = None


# Allowed event type values for the event notification endpoint
EventType = Literal[
    "document_uploaded",
    "document_verified",
    "document_rejected",
    "status_update",
    "action_required",
    "general",
]


class SendEventNotificationRequest(BaseModel):
    """
    Universal event notification request.  Can be sent by any authenticated
    user â€” HR, admin, or candidate.

    Example use-cases:
    - Candidate uploads a document â†’ call with event_type="document_uploaded"
      to_email = HR's email, recipient_name = HR's name
    - HR verifies a document â†’ event_type="document_verified"
      to_email = candidate's email, recipient_name = candidate's name
    - Any status change â†’ event_type="status_update"
    """
    to_email: EmailStr
    recipient_name: str
    event_type: EventType = "general"
    heading: str
    message: str
    cc_emails: Optional[List[EmailStr]] = None
    metadata: Optional[Dict[str, str]] = None  # Extra key-value details shown in the email table
    action_url: Optional[str] = None           # Optional CTA deep-link button URL
    action_label: str = "View Details"         # Label for the CTA button

class SendInterviewInviteRequest(BaseModel):
    """
    Send a full interview invite (Teams event + candidate email) using
    candidate and interview IDs already in the system.
    """
    interview_id: int
    extra_notes: Optional[str] = ""
    timezone: Optional[str] = "Asia/Kolkata"
    create_teams_event: Optional[bool] = True


class SendCustomInterviewInviteRequest(BaseModel):
    """
    Ad-hoc invite when you don't have an interview_id yet (free-form).
    """
    candidate_email: EmailStr
    candidate_name: str
    round_name: str
    start_time_iso: str
    end_time_iso: str
    interviewer_emails: List[EmailStr]
    extra_notes: Optional[str] = ""
    timezone: Optional[str] = "Asia/Kolkata"
    create_teams_event: Optional[bool] = True


class SendLoginCredentialsRequest(BaseModel):
    """
    Optional override for the portal link.
    The candidate's email and password are read directly from the database.
    """
    portal_link: Optional[str] = "https://hrms.blitzenx.com/"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Endpoints
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post(
    "/send",
    dependencies=[Depends(get_current_user)],

    summary="Send a plain or HTML email from the HRMS service mailbox",
)
def send_mail(
    request: SendMailRequest,
    current_user=Depends(get_current_internal_user),
):
    """
    Send an email from **helpdesk_hrms@blitzenx.com** to any recipient.
    Supports plain text and HTML body. Optional CC list.
    """
    logger.info(
        f"[email/send] Triggered by {current_user.UserEmail} â†’ {request.to_email}"
    )
    return EmailService.send_email(
        to_email=request.to_email,
        subject=request.subject,
        body_content=request.body_content,
        is_html=request.is_html,
        cc_emails=request.cc_emails,
    )


@router.post(
    "/send-with-attachments",
    dependencies=[Depends(get_current_user)],

    summary="Send an email with one or more file attachments",
)
async def send_mail_with_attachments(
    to_email: str = Form(..., description="Recipient email address"),
    subject: str = Form(..., description="Email subject line"),
    body_content: str = Form(..., description="Email body (HTML or plain text)"),
    is_html: bool = Form(True, description="Set false for plain text"),
    cc_emails: Optional[str] = Form(
        None,
        description="Comma-separated CC email addresses, e.g. a@x.com,b@x.com",
    ),
    files: List[UploadFile] = File(
        default=[],
        description="One or more files to attach (PDF, DOCX, images, etc.)",
    ),
    current_user=Depends(get_current_internal_user),
):
    """
    Send an email **with file attachments** from helpdesk_hrms@blitzenx.com.

    Use `multipart/form-data`. Attach one or more files using the `files` field.
    Microsoft Graph supports up to **3 MB total** via this inline method; for
    larger files use the upload-session approach.
    """
    # Parse comma-separated CC list
    cc_list: Optional[List[str]] = None
    if cc_emails:
        cc_list = [e.strip() for e in cc_emails.split(",") if e.strip()]

    # Read all uploaded files into memory
    attachments = []
    total_size = 0
    for upload in files:
        content = await upload.read()
        total_size += len(content)
        if total_size > 3 * 1024 * 1024:   # 3 MB safety limit
            raise HTTPException(
                status_code=413,
                detail="Total attachment size exceeds 3 MB. Use smaller files.",
            )
        attachments.append(
            {
                "name": upload.filename or "attachment",
                "content": content,
                "content_type": upload.content_type or "application/octet-stream",
            }
        )

    logger.info(
        f"[email/send-with-attachments] {current_user.UserEmail} â†’ {to_email} "
        f"| Files: {[f['name'] for f in attachments]}"
    )

    return EmailService.send_email(
        to_email=to_email,
        subject=subject,
        body_content=body_content,
        is_html=is_html,
        cc_emails=cc_list,
        attachments=attachments if attachments else None,
    )


@router.post(
    "/notify",
    dependencies=[Depends(get_current_user)],

    summary="Send a styled HRMS notification email",
)
def send_notification(
    request: SendNotificationRequest,
    current_user=Depends(get_current_internal_user),
):
    """
    Send a branded notification email with a heading and body message.
    Uses the BlitzenX HRMS email template automatically.
    """
    logger.info(
        f"[email/notify] Triggered by {current_user.UserEmail} â†’ {request.to_email} | {request.heading}"
    )
    return EmailService.send_notification(
        to_email=request.to_email,
        heading=request.heading,
        message=request.message,
        cc_emails=request.cc_emails,
    )


@router.post(
    "/notify/event",
    dependencies=[Depends(require_resource_permission("message", "send"))],
    summary="Send a rich event notification email (open to any authenticated user)",
    response_description="Email send result",
)
def send_event_notification(
    request: SendEventNotificationRequest,
    current_user=Depends(get_current_user),
):
    """
    Universal event-driven notification email endpoint.

    **Who can call this?**
    Any authenticated user â€” HR users, admins, **and candidates** â€” all share this
    single endpoint.  Authentication is JWT-based (`get_current_user` resolves
    both `Users` and `Candidate` token types).

    **Supported `event_type` values:**

    | Value | Colour | Use-case |
    |---|---|---|
    | `document_uploaded` | ðŸ”µ Blue | Candidate uploaded a document â†’ notify HR |
    | `document_verified` | ðŸŸ¢ Green | HR verified a document â†’ notify candidate |
    | `document_rejected` | ðŸ”´ Red | HR rejected a document â†’ notify candidate |
    | `status_update` | ðŸŸ£ Purple | Pipeline/status changed |
    | `action_required` | ðŸŸ¡ Amber | Something needs attention |
    | `general` | âš« Grey | Generic catch-all notification |

    **`metadata`** (optional): A flat key-value dict rendered as a detail table
    inside the email.  Example:
    ```json
    {
      "Candidate": "John Doe",
      "Document": "Aadhaar Card",
      "Uploaded At": "2026-06-15 10:30 IST"
    }
    ```

    **`action_url`** (optional): A CTA button deep-link rendered inside the email
    (e.g. a link to the candidate's profile or the document review page).

    The caller's display name is automatically attached as a *"triggered by"*
    footer note in the email body.
    """
    # â”€â”€ Resolve caller display name â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if isinstance(current_user, Users):
        caller_name = current_user.UserName or current_user.UserEmail
        caller_ref = current_user.UserEmail
    else:
        # Candidate
        caller_name = " ".join(
            filter(None, [current_user.candidateFirstName, current_user.candidateLastName])
        ) or current_user.candidateEmail
        caller_ref = current_user.candidateEmail

    logger.info(
        f"[email/notify/event] Triggered by {caller_ref} | type={request.event_type} "
        f"â†’ {request.to_email} | {request.heading}"
    )

    return EmailService.send_event_notification(
        to_email=request.to_email,
        recipient_name=request.recipient_name,
        event_type=request.event_type,
        heading=request.heading,
        message=request.message,
        cc_emails=list(request.cc_emails) if request.cc_emails else None,
        metadata=request.metadata,
        action_url=request.action_url,
        action_label=request.action_label,
        triggered_by_name=caller_name,
    )

@router.post(
    "/interview/invite/{interview_id}",
    dependencies=[Depends(get_current_user)],

    summary="Send interview invite for an existing scheduled interview",
)
def send_interview_invite_by_id(
    interview_id: int,
    extra_notes: str = "",
    timezone: str = "Asia/Kolkata",
    create_teams_event: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """
    Fetches interview details from the DB (candidate, panel members, times)
    and sends a full invite:
    - Creates a Teams calendar event (organiser = helpdesk_hrms@blitzenx.com)
    - Sends a branded HTML email to the **candidate** with interviewers in CC

    Also stores the `outlook_event_id` and `meeting_link` back on the interview row.
    """
    # â”€â”€ Load interview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")

    # â”€â”€ Load candidate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == interview.candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(
            status_code=404, detail=f"Candidate {interview.candidate_id} not found"
        )

    candidate_name = " ".join(
        filter(None, [candidate.candidateFirstName, candidate.candidateLastName])
    ) or "Candidate"
    candidate_email = candidate.candidateEmail

    # â”€â”€ Load panel round name â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    round_name = panel.round_name if panel else "Interview"

    # â”€â”€ Load panel member (interviewer) emails â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    members = (
        db.query(PanelMember)
        .filter(PanelMember.panel_id == interview.panel_id)
        .all()
    )
    interviewer_emails: List[str] = []
    for m in members:
        user = db.query(Users).filter(Users.UserID == m.interviewer_id).first()
        if user and user.UserEmail:
            interviewer_emails.append(user.UserEmail)

    # â”€â”€ Format times â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    start_iso = interview.start_time.isoformat() if interview.start_time else ""
    end_iso = interview.end_time.isoformat() if interview.end_time else ""

    if not start_iso or not end_iso:
        raise HTTPException(
            status_code=400,
            detail="Interview start/end times are not set. Update the interview first.",
        )

    logger.info(
        f"[email/interview/invite] {current_user.UserEmail} â†’ "
        f"Candidate: {candidate_email} | Round: {round_name} | Interviewers: {interviewer_emails}"
    )

    # â”€â”€ Send invite (creates Teams event + sends email) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    result = EmailService.send_interview_invite(
        candidate_email=candidate_email,
        candidate_name=candidate_name,
        round_name=round_name,
        start_time_iso=start_iso,
        end_time_iso=end_iso,
        interviewer_emails=interviewer_emails,
        extra_notes=extra_notes,
        timezone=timezone,
        create_teams_event=create_teams_event,
    )

    # â”€â”€ Persist event details back to the interview row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if result.get("eventId"):
        interview.outlook_event_id = result["eventId"]
    if result.get("joinUrl"):
        interview.meeting_link = result["joinUrl"]
    db.commit()

    return result


@router.delete(
    "/interview/cancel/{interview_id}",
    dependencies=[Depends(get_current_user)],

    summary="Cancel a scheduled interview â€” removes the Teams event and notifies everyone",
)
def cancel_interview_by_id(
    interview_id: int,
    reason: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """
    Cancels an existing interview by its ID.

    **What this does:**
    - Deletes the Teams / Outlook calendar event from the HRMS service mailbox via
      Microsoft Graph (so it disappears from every attendee's calendar).
    - Sends a branded cancellation email to the **candidate** with all panel
      interviewers in **CC**, optionally including the reason provided.
    - Marks the interview `status` as `"Cancelled"` in the database and clears
      `meeting_link` / `outlook_event_id`.

    **`reason`** (optional query param) â€” e.g. *"Candidate not available"*.
    If omitted, the email will still be sent without a reason clause.
    """
    # â”€â”€ Load interview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")

    if interview.status == "Cancelled":
        raise HTTPException(
            status_code=400,
            detail=f"Interview {interview_id} is already cancelled.",
        )

    # â”€â”€ Load candidate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == interview.candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(
            status_code=404, detail=f"Candidate {interview.candidate_id} not found"
        )

    candidate_name = " ".join(
        filter(None, [candidate.candidateFirstName, candidate.candidateLastName])
    ) or "Candidate"
    candidate_email = candidate.candidateEmail

    # â”€â”€ Load panel round name â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    round_name = panel.round_name if panel else "Interview"

    # â”€â”€ Load panel member (interviewer) emails â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    members = (
        db.query(PanelMember)
        .filter(PanelMember.panel_id == interview.panel_id)
        .all()
    )
    interviewer_emails: List[str] = []
    for m in members:
        user = db.query(Users).filter(Users.UserID == m.interviewer_id).first()
        if user and user.UserEmail:
            interviewer_emails.append(user.UserEmail)

    start_iso = interview.start_time.isoformat() if interview.start_time else "N/A"

    logger.info(
        f"[email/interview/cancel] {current_user.UserEmail} â†’ "
        f"Interview {interview_id} | Candidate: {candidate_email} | Reason: {reason!r}"
    )

    # â”€â”€ Cancel Teams event + send email â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    result = EmailService.cancel_interview_event(
        outlook_event_id=interview.outlook_event_id or "",
        candidate_email=candidate_email,
        candidate_name=candidate_name,
        round_name=round_name,
        start_time_iso=start_iso,
        interviewer_emails=interviewer_emails,
        reason=reason,
    )

    # â”€â”€ Update interview record in DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    interview.status = "Cancelled"
    interview.meeting_link = None
    interview.outlook_event_id = None
    db.commit()

    return result


@router.post(
    "/interview/invite/custom",
    dependencies=[Depends(get_current_user)],

    summary="Send a custom ad-hoc interview invite (no interview_id needed)",
)
def send_custom_interview_invite(
    request: SendCustomInterviewInviteRequest,
    current_user=Depends(get_current_internal_user),
):
    """
    Ad-hoc interview invite when the interview hasn't been formally
    entered into the system yet. Provide all details manually.
    """
    logger.info(
        f"[email/interview/invite/custom] {current_user.UserEmail} â†’ "
        f"{request.candidate_email} | Round: {request.round_name}"
    )
    return EmailService.send_interview_invite(
        candidate_email=request.candidate_email,
        candidate_name=request.candidate_name,
        round_name=request.round_name,
        start_time_iso=request.start_time_iso,
        end_time_iso=request.end_time_iso,
        interviewer_emails=request.interviewer_emails,
        extra_notes=request.extra_notes or "",
        timezone=request.timezone or "Asia/Kolkata",
        create_teams_event=request.create_teams_event,
    )


@router.post(
    "/login-credentials/{candidate_id}",
    dependencies=[Depends(get_current_user)],

    summary="Send login credentials to a candidate via email",
)
def send_login_credentials(
    candidate_id: str,
    request: SendLoginCredentialsRequest = SendLoginCredentialsRequest(),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """
    Looks up the candidate by **candidate_id** and sends a branded HTML email
    to their registered email address containing their login credentials and a
    direct link to the HRMS portal.

    Both the **email address** (`candidateEmail`) and the **plain-text password**
    (`candidateTempPassword`) are read automatically from the candidate record in
    the database â€” no manual input is needed.

    Returns **400** if the candidate's plain-text password is not stored
    (e.g. candidates created before this feature). In that case, reset their
    password via the change-password endpoint first.
    """
    # â”€â”€ Load candidate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )

    candidate_name = " ".join(
        filter(None, [candidate.candidateFirstName, candidate.candidateLastName])
    ) or "Candidate"

    # â”€â”€ Read email and plain-text password from DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    login_email: str = candidate.candidateEmail
    plain_password: str = candidate.candidateTempPassword
    portal_link: str = request.portal_link or "https://hrms.blitzenx.com/"

    if not login_email:
        raise HTTPException(
            status_code=400,
            detail="No email address found for this candidate.",
        )
    if not plain_password:
        raise HTTPException(
            status_code=400,
            detail=(
                "Plain-text password is not stored for this candidate. "
                "Reset their password via the change-password endpoint â€” "
                "the new password will be saved and can then be emailed."
            ),
        )

    logger.info(
        f"[email/login-credentials] {current_user.UserEmail} â†’ "
        f"Candidate: {candidate_id} ({login_email})"
    )

    return EmailService.send_login_credentials(
        candidate_email=login_email,
        candidate_name=candidate_name,
        login_email=login_email,
        password=plain_password,
        portal_link=portal_link,
    )
