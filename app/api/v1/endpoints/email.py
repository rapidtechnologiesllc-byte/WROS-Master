"""
HRMS Email Service Endpoints
Provides production-ready mail & interview scheduling APIs backed by
Microsoft Graph via helpdesk_hrms@blitzenx.com.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.core.logging import logger
from app.models import Candidate, Interview, InterviewPanel, PanelMember, Users
from app.services.email_service import EmailService

router = APIRouter(prefix="/email", tags=["Email Service"])


# ──────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/send",
    dependencies=[Depends(require_permission("interview.manage"))],
    summary="Send a plain or HTML email from the HRMS service mailbox",
)
def send_mail(
    request: SendMailRequest,
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Send an email from **helpdesk_hrms@blitzenx.com** to any recipient.
    Supports plain text and HTML body. Optional CC list.
    """
    logger.info(
        f"[email/send] Triggered by {current_user.UserEmail} → {request.to_email}"
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
    dependencies=[Depends(require_permission("interview.manage"))],
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
    current_user=Depends(get_current_hr_or_admin),
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
        f"[email/send-with-attachments] {current_user.UserEmail} → {to_email} "
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
    dependencies=[Depends(require_permission("interview.manage"))],
    summary="Send a styled HRMS notification email",
)
def send_notification(
    request: SendNotificationRequest,
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Send a branded notification email with a heading and body message.
    Uses the BlitzenX HRMS email template automatically.
    """
    logger.info(
        f"[email/notify] Triggered by {current_user.UserEmail} → {request.to_email} | {request.heading}"
    )
    return EmailService.send_notification(
        to_email=request.to_email,
        heading=request.heading,
        message=request.message,
        cc_emails=request.cc_emails,
    )


@router.post(
    "/interview/invite/{interview_id}",
    dependencies=[Depends(require_permission("interview.manage"))],
    summary="Send interview invite for an existing scheduled interview",
)
def send_interview_invite_by_id(
    interview_id: int,
    extra_notes: str = "",
    timezone: str = "Asia/Kolkata",
    create_teams_event: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Fetches interview details from the DB (candidate, panel members, times)
    and sends a full invite:
    - Creates a Teams calendar event (organiser = helpdesk_hrms@blitzenx.com)
    - Sends a branded HTML email to the **candidate** with interviewers in CC

    Also stores the `outlook_event_id` and `meeting_link` back on the interview row.
    """
    # ── Load interview ──────────────────────────────────────────────────────
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")

    # ── Load candidate ──────────────────────────────────────────────────────
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

    # ── Load panel round name ───────────────────────────────────────────────
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    round_name = panel.round_name if panel else "Interview"

    # ── Load panel member (interviewer) emails ──────────────────────────────
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

    # ── Format times ────────────────────────────────────────────────────────
    start_iso = interview.start_time.isoformat() if interview.start_time else ""
    end_iso = interview.end_time.isoformat() if interview.end_time else ""

    if not start_iso or not end_iso:
        raise HTTPException(
            status_code=400,
            detail="Interview start/end times are not set. Update the interview first.",
        )

    logger.info(
        f"[email/interview/invite] {current_user.UserEmail} → "
        f"Candidate: {candidate_email} | Round: {round_name} | Interviewers: {interviewer_emails}"
    )

    # ── Send invite (creates Teams event + sends email) ─────────────────────
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

    # ── Persist event details back to the interview row ─────────────────────
    if result.get("eventId"):
        interview.outlook_event_id = result["eventId"]
    if result.get("joinUrl"):
        interview.meeting_link = result["joinUrl"]
    db.commit()

    return result


@router.post(
    "/interview/invite/custom",
    dependencies=[Depends(require_permission("interview.manage"))],
    summary="Send a custom ad-hoc interview invite (no interview_id needed)",
)
def send_custom_interview_invite(
    request: SendCustomInterviewInviteRequest,
    current_user=Depends(get_current_hr_or_admin),
):
    """
    Ad-hoc interview invite when the interview hasn't been formally
    entered into the system yet. Provide all details manually.
    """
    logger.info(
        f"[email/interview/invite/custom] {current_user.UserEmail} → "
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
