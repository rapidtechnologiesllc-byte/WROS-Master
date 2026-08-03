"""
S-049/HRMS-0449 -- Interview Confirmation via Thunder.

Real architecture adaptations:
- No new `interviews` table -- confirms the existing `SubmissionInterview`
  row S-048/HRMS-0448 created. "status=CONFIRMED" (spec's own literal
  value) maps to a new `confirmed_at` timestamp column (added this
  story) being set -- there's no separate literal status enum on this
  row, same "presence of a timestamp IS the state" convention
  `scheduled_at` already established for "status=SCHEDULED".
  `scheduled_via_graph_event_id` (already existed, reserved by
  HRMS-0448's own docstring for exactly this) is populated for real
  here with the actual Graph event ID.
- BR-01 (send via BOTH WhatsApp and email, ignoring channel
  preference): WhatsApp still goes through
  `thunder_service.send_thunder_message()` -- this codebase's one
  required send path (R-08 ownership, consent, and debounce all still
  apply; those are hard invariants, not preference logic, so they are
  NOT bypassed even though channel *preference* is). Email has no
  equivalent gated path anywhere in this codebase (every existing
  candidate-facing email already goes out ungated via
  `EmailService.send_email()` directly -- established convention, see
  S-041's own docstring) and additionally needs an attachment, which
  `send_outbound_campaign_message()` doesn't support -- so email is
  sent directly via `EmailService.send_email(..., attachments=[...])`,
  with its own `ConversationEvent` logged manually to keep the real
  message log complete, matching the same manual-logging convention
  every other direct-EmailService call in this codebase already uses.
  If WhatsApp fails for a real, structural reason (no consent, human
  owns the conversation, duplicate-suppressed), that failure is logged
  and swallowed -- email is NOT blocked by it, per BR-01's own
  reasoning ("too important to risk on a single channel").
- No `.ics` library exists in this codebase (checked -- `icalendar` is
  not installed) -- `build_ics_file()` hand-builds a minimal, valid
  VCALENDAR/VEVENT text block directly from the spec's own literal
  field list (DTSTART/DTEND in UTC `Z` form, SUMMARY, DESCRIPTION,
  LOCATION, ORGANIZER), rather than adding a new dependency for a
  handful of fields.
- Step 3's Outlook event creation reuses the same minimal, injectable
  Graph `POST /events` REST pattern S-048/HRMS-0448 already established
  in `calendar_matching_service.py` (own call, not a refactor of the
  existing HR-facing `msgraph.py` endpoint, which requires FastAPI
  `Depends` injection and can't be called as a plain function anyway).
- No "candidate profile summary" generation exists for this purpose --
  the interviewer's calendar invite body includes the job title
  (`Demand.job_title`) and the real resume link
  (`Submission.submitted_as_resume_url`, the one real resume-URL field
  that exists anywhere in this codebase per its own model comment
  -- `Candidate` itself has no resume_url column) when present, rather
  than fabricating a summary paragraph.
- No real video-conferencing link generation exists (explicitly out of
  scope per this story's own "What NOT to build" -- "link provided
  manually or via future integration"). `interview.notes` is read as an
  optional recruiter-provided meeting link/phone number; if empty, the
  candidate and interviewer messages honestly say details will follow,
  rather than inventing a placeholder link.
- No `INTERVIEW_SCHEDULED` conversation-state enum value exists (same
  fictional 10-state enum every S-041-048 story has already flagged).
  `transitionState(..., 'INTERVIEW_SCHEDULED')` is logged as a real
  `ConversationEvent` (`INTERVIEW_CONFIRMED`) instead.
- No internal event bus -- "publish interview.confirmed, triggers
  HRMS-0450 Reminder Engine" has no bus to publish through, and
  HRMS-0450 doesn't exist in this codebase yet either. The
  `INTERVIEW_CONFIRMED` `ConversationEvent` IS the real, durable signal
  a future HRMS-0450 build would read directly -- same posture every
  other "downstream story not built yet" case this round has taken.
- Deliberately NOT wired into a live trigger yet -- same posture
  S-047/S-048 already took. `confirm_interview()` is the real, callable,
  fully tested entry point a future wiring pass would call right after
  `calendar_matching_service.attempt_calendar_match()` returns
  `outcome="matched"`.
"""
import os
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Callable, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.submission import Submission
from app.models.user import Users
from app.services.email_service import EmailService
from app.services.notification_service import send_notification
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, send_thunder_message

DEFAULT_ORGANIZER_EMAIL = os.getenv("THUNDER_ORGANIZER_EMAIL", "thunder@blitzenx.com")
GraphCreateEventCall = Callable[[str, str, str, str, str, str, list], str]


def _as_utc(dt: datetime) -> datetime:
    """SubmissionInterview.scheduled_at is a plain DateTime column
    (BR-01 stores it in UTC, but SQLite/older drivers can round-trip it
    naive) -- always treat a naive value as UTC, never local."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def _ics_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build_ics_file(*, uid: str, summary: str, description: str, location: str, start_utc: datetime, end_utc: datetime, organizer_email: str = DEFAULT_ORGANIZER_EMAIL) -> bytes:
    """Step 2. Minimal, valid VCALENDAR/VEVENT text -- no icalendar
    library installed in this codebase, hand-built from the spec's own
    literal field list."""
    def fmt(dt: datetime) -> str:
        return dt.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BlitzenX//Thunder//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{fmt(datetime.now(dt_timezone.utc))}",
        f"DTSTART:{fmt(start_utc)}",
        f"DTEND:{fmt(end_utc)}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"LOCATION:{_ics_escape(location)}",
        f"ORGANIZER:mailto:{organizer_email}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _default_graph_create_event_call(organizer_email: str, subject: str, start_iso: str, end_iso: str, timezone: str, body: str, attendees: list) -> str:
    import requests
    from app.core.graph_auth import get_graph_token

    access_token = get_graph_token()
    endpoint = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events"
    payload = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
        "body": {"contentType": "Text", "content": body},
        "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in attendees],
    }
    resp = requests.post(endpoint, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["id"]


def _resolve_interviewer_user(db: Session, panel: Optional[DemandInterviewPanel]) -> Optional[Users]:
    if panel is None:
        return None
    employee = db.query(Employee).filter(Employee.id == panel.employee_id).first()
    if employee is None or not employee.wros_user_id:
        return None
    return db.query(Users).filter(Users.UserID == employee.wros_user_id).first()


def _notify_recruiter(db: Session, submission: Submission, message: str) -> None:
    if not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP", message=message,
        )
    except Exception as exc:
        logger.warning(f"[InterviewConfirmation] Failed to notify recruiter for submission {submission.id!r}: {exc}")


def confirm_interview(
    db: Session, interview_id: str, candidate: Candidate, conversation: CandidateConversation, *, graph_create_event_call: Optional[GraphCreateEventCall] = None,
) -> Dict:
    """Never raises. Returns one of:
      {"outcome": "interview_not_found"}
      {"outcome": "confirmed", "whatsapp_sent": bool, "email_sent": bool, "calendar_event_id": Optional[str], "calendar_invite_failed": bool}
    """
    try:
        interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == interview_id).first()
        if interview is None or interview.scheduled_at is None:
            return {"outcome": "interview_not_found"}

        submission = db.query(Submission).filter(Submission.id == interview.submission_id).first()
        demand = db.query(Demand).filter(Demand.id == submission.demand_id).first() if submission else None
        panel = db.query(DemandInterviewPanel).filter(DemandInterviewPanel.id == interview.panel_id).first() if interview.panel_id else None
        interviewer_user = _resolve_interviewer_user(db, panel)
        interviewer_employee = db.query(Employee).filter(Employee.id == panel.employee_id).first() if panel else None

        scheduled_utc = _as_utc(interview.scheduled_at)
        duration_minutes = 60
        end_utc = scheduled_utc + timedelta(minutes=duration_minutes)

        candidate_tz = ZoneInfo(candidate.timezone or "Asia/Kolkata")
        candidate_local = scheduled_utc.astimezone(candidate_tz)
        interviewer_name = f"{interviewer_employee.first_name} {interviewer_employee.last_name}".strip() if interviewer_employee else "our interviewer"
        job_title = demand.job_title if demand else "the role"
        meeting_detail = interview.notes.strip() if interview.notes else "Details will be shared closer to the interview date."

        candidate_message = (
            f"Great news, {candidate.candidateFirstName or 'there'}! Your interview with {interviewer_name} at BlitzenX is confirmed. "
            f"Date: {candidate_local.strftime('%A, %b %d, %Y')}. Time: {candidate_local.strftime('%I:%M %p %Z')}. "
            f"Duration: {duration_minutes} minutes. {meeting_detail} We are excited to learn more about your background!"
        )

        whatsapp_sent = False
        try:
            send_thunder_message(db, conversation, candidate, candidate_message, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
            whatsapp_sent = True
        except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed) as exc:
            logger.info(f"[InterviewConfirmation] WhatsApp confirmation skipped for candidate {candidate.candidateID!r}: {exc}")

        ics_bytes = build_ics_file(
            uid=f"interview-{interview.id}@blitzenx.com", summary="Interview with BlitzenX", description=f"Interview with {interviewer_name}",
            location=meeting_detail, start_utc=scheduled_utc, end_utc=end_utc,
        )
        email_body = (
            f"<p>{candidate_message}</p>"
            f"<p>Add this to your calendar using the attached invite.</p>"
        )
        email_sent = False
        try:
            EmailService.send_email(
                candidate.candidateEmail, "Your BlitzenX Interview is Confirmed", email_body, is_html=True,
                attachments=[{"name": "interview_confirmation.ics", "content": ics_bytes, "content_type": "text/calendar"}],
            )
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="ai_message_sent", event_data={"channel": "email", "body": email_body[:500], "auto_generated": True}, triggered_by="ai_agent"))
            email_sent = True
        except Exception as exc:
            logger.error(f"[InterviewConfirmation] CONFIRMATION_EMAIL_FAILED for candidate {candidate.candidateID!r}: {exc}")
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="CONFIRMATION_EMAIL_FAILED", event_data={"reason": str(exc)}, triggered_by="system"))

        calendar_event_id = None
        calendar_invite_failed = False
        if interviewer_user is not None:
            interviewer_tz_name = interviewer_user.timezone or "Asia/Kolkata"
            interviewer_local = scheduled_utc.astimezone(ZoneInfo(interviewer_tz_name))
            subject = f"Interview: {candidate.candidateFirstName or candidate.candidateID} \u2014 {job_title}"
            body_lines = [f"Candidate: {candidate.candidateFirstName or candidate.candidateID}", f"Job Title: {job_title}"]
            if submission and submission.submitted_as_resume_url:
                body_lines.append(f"Resume: {submission.submitted_as_resume_url}")
            call = graph_create_event_call or _default_graph_create_event_call
            try:
                calendar_event_id = call(
                    interviewer_user.UserEmail, subject, interviewer_local.isoformat(), (interviewer_local + timedelta(minutes=duration_minutes)).isoformat(),
                    interviewer_tz_name, "\n".join(body_lines), [interviewer_user.UserEmail],
                )
                interview.scheduled_via_graph_event_id = calendar_event_id
            except Exception as exc:
                calendar_invite_failed = True
                logger.error(f"[InterviewConfirmation] CALENDAR_INVITE_FAILED for interview {interview.id!r}: {exc}")
                db.add(ConversationEvent(conversation_id=conversation.id, event_type="CALENDAR_INVITE_FAILED", event_data={"reason": str(exc)}, triggered_by="system"))
                try:
                    EmailService.send_email(interviewer_user.UserEmail, subject, "\n".join(body_lines) + f"\n\nTime: {interviewer_local.strftime('%A, %b %d, %Y %I:%M %p %Z')}", is_html=False)
                except Exception as email_exc:
                    logger.error(f"[InterviewConfirmation] Interviewer fallback email also failed: {email_exc}")
                if submission:
                    _notify_recruiter(db, submission, f"Outlook calendar invite failed for {candidate.candidateFirstName or candidate.candidateID}'s interview -- interviewer was emailed directly as a fallback.")
        else:
            calendar_invite_failed = True
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="CALENDAR_INVITE_FAILED", event_data={"reason": "no_interviewer_user_resolved"}, triggered_by="system"))

        interview.confirmed_at = datetime.utcnow()
        db.add(interview)
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="INTERVIEW_CONFIRMED",
            event_data={"candidate_id": candidate.candidateID, "interview_id": interview.id, "scheduled_at_utc": scheduled_utc.isoformat()}, triggered_by="system",
        ))
        db.commit()

        return {
            "outcome": "confirmed", "whatsapp_sent": whatsapp_sent, "email_sent": email_sent,
            "calendar_event_id": calendar_event_id, "calendar_invite_failed": calendar_invite_failed,
        }
    except Exception as exc:
        logger.error(f"[InterviewConfirmation] Unexpected failure confirming interview {interview_id!r}: {exc}")
        db.rollback()
        return {"outcome": "confirmation_failed"}
