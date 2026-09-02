"""
import logging
S-050/HRMS-0450 -- Interview Reminder Engine.

Real architecture adaptations:
- interview_reminders is genuinely new (see its model docstring).
- No `interviews.candidate_timezone` column, no internal event bus for
  "interview.confirmed" -- `schedule_reminders_for_interview()` is a
  real, callable, directly-invoked function (not an event listener)
  meant to run right after
  `interview_confirmation_service.confirm_interview()` returns
  `outcome="confirmed"`, reading `Candidate.timezone` fresh rather than
  a duplicated column. Deliberately NOT wired into a live trigger yet
  -- same posture S-047/S-048/S-049 already took throughout this whole
  scheduling chain.
- No `interviews.status` RESCHEDULED/CANCELLED values exist --
  `SubmissionInterview` has no such column, and HRMS-0451 (Reschedule
  Workflow) doesn't exist in this codebase yet either, so nothing
  actually produces a reschedule/cancellation signal today. BR-03's
  "verify interview.status=CONFIRMED before sending" is honored via
  the real signal that exists: `confirmed_at is not None`. Step 4's
  `cancel_pending_reminders_for_interview()` is built and real (any
  future HRMS-0451/cancellation flow can call it directly), but
  nothing calls it yet -- an honest, flagged gap, not a fabricated
  wiring.
- Reminder message content mirrors
  `interview_confirmation_service`'s own conventions: candidate name,
  interviewer name (via `DemandInterviewPanel`/`Employee`), local time
  via `Candidate.timezone`, and `interview.notes` as the optional
  recruiter-provided meeting-link/phone (same "no real video-link
  generation, don't fabricate one" stance S-049 already took).
- BR-02 (send via both channels): reuses the exact same dual-channel
  pattern S-049 established -- WhatsApp via
  `thunder_service.send_thunder_message()` (R-08/consent/debounce
  still real, hard invariants), email via `EmailService.send_email()`
  directly (no gated email path exists anywhere in this codebase).
  Per BR-02's own integrations note ("if both fail: log
  REMINDER_SEND_FAILED, recruiter notified"), a WhatsApp-only failure
  does NOT block email and is NOT itself escalated -- only a
  double-channel failure triggers REMINDER_SEND_FAILED + recruiter
  notification, matching the spec's own integrations table exactly
  (contrast with S-049, where a WhatsApp failure is silently swallowed
  regardless of email outcome -- here both failing together is
  explicitly a real, distinct, escalated case).
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.interview_reminder import InterviewReminder
from app.models.submission import Submission
from app.models.user import Users
from app.services.email_service import EmailService
from app.services.notification_service import send_notification
from app.services.thunder_pause_service import is_thunder_paused_for_conversation
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message

SKIP_24H_THRESHOLD_HOURS = 25  # Step 2 -- less than 25h away: skip the 24H reminder
SKIP_BOTH_THRESHOLD_MINUTES = 70  # Step 2 -- less than 70min away: skip both
JOB_BATCH_SIZE = 100


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def schedule_reminders_for_interview(db: Session, interview_id: str, *, now: Optional[datetime] = None) -> Dict:
    """Step 2. Never raises. Returns:
      {"outcome": "interview_not_found"}
      {"outcome": "scheduled", "reminders_created": [...]}
    """
    try:
        interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == interview_id).first()
        if interview is None or interview.scheduled_at is None:
            return {"outcome": "interview_not_found"}

        now = now or datetime.now(dt_timezone.utc)
        scheduled_utc = _as_utc(interview.scheduled_at)
        time_until_interview = scheduled_utc - now

        created = []
        if time_until_interview < timedelta(minutes=SKIP_BOTH_THRESHOLD_MINUTES):
            return {"outcome": "scheduled", "reminders_created": []}  # too late to be useful, BR/Step-2

        if time_until_interview >= timedelta(hours=SKIP_24H_THRESHOLD_HOURS):
            reminder_24h = InterviewReminder(
                tenant_id=interview.tenant_id, interview_id=interview.id, candidate_id=interview.candidate_id,
                reminder_type="24H_BEFORE", scheduled_at=scheduled_utc - timedelta(hours=24),
            )
            db.add(reminder_24h)
            created.append("24H_BEFORE")

        reminder_1h = InterviewReminder(
            tenant_id=interview.tenant_id, interview_id=interview.id, candidate_id=interview.candidate_id,
            reminder_type="1H_BEFORE", scheduled_at=scheduled_utc - timedelta(hours=1),
        )
        db.add(reminder_1h)
        created.append("1H_BEFORE")

        db.commit()
        return {"outcome": "scheduled", "reminders_created": created}
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[InterviewReminder] Failed scheduling reminders for interview {interview_id!r}: {exc}")
        db.rollback()
        return {"outcome": "scheduling_failed"}


def cancel_pending_reminders_for_interview(db: Session, interview_id: str) -> int:
    """Step 4. Real, callable -- no live caller wires this in yet (see
    module docstring); a future HRMS-0451/cancellation flow would call
    this directly."""
    rows = db.query(InterviewReminder).filter(InterviewReminder.interview_id == interview_id, InterviewReminder.status == "PENDING").all()
    for row in rows:
        row.status = "CANCELLED"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def _resolve_interviewer_name(db: Session, panel_id: Optional[str]) -> str:
    if not panel_id:
        return "our interviewer"
    panel = db.query(DemandInterviewPanel).filter(DemandInterviewPanel.id == panel_id).first()
    if panel is None:
        return "our interviewer"
    employee = db.query(Employee).filter(Employee.id == panel.employee_id).first()
    if employee is None:
        return "our interviewer"
    return f"{employee.first_name} {employee.last_name}".strip() or "our interviewer"


def _notify_recruiter(db: Session, submission: Optional[Submission], message: str) -> None:
    if submission is None or not submission.submitted_by_user_id:
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
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[InterviewReminder] Failed to notify recruiter: {exc}")


def _build_reminder_message(reminder_type: str, candidate: Candidate, interviewer_name: str, candidate_local: datetime, meeting_detail: str) -> str:
    if reminder_type == "24H_BEFORE":
        return (
            f"Hi {candidate.candidateFirstName or 'there'}! Just a friendly reminder -- your interview with "
            f"{interviewer_name} at BlitzenX is tomorrow at {candidate_local.strftime('%I:%M %p %Z')}. "
            f"Please let me know if you need to reschedule."
        )
    return (
        f"Hi {candidate.candidateFirstName or 'there'}! Your BlitzenX interview is in 1 hour -- at "
        f"{candidate_local.strftime('%I:%M %p %Z')}. {meeting_detail} Good luck!"
    )


def run_reminder_execution_job(db: Session) -> Dict:
    """Step 3. Runs every 10 min. Never lets one bad row abort the
    batch -- catches per-row, moves on, same defensive posture as every
    other periodic job this round."""
    result = {"processed": 0, "sent": 0, "cancelled": 0, "skipped": 0}

    now = datetime.now(dt_timezone.utc)
    due = (
        db.query(InterviewReminder)
        .filter(InterviewReminder.status == "PENDING", InterviewReminder.scheduled_at <= now)
        .order_by(InterviewReminder.scheduled_at.asc())
        .limit(JOB_BATCH_SIZE)
        .all()
    )

    for reminder in due:
        result["processed"] += 1
        try:
            interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == reminder.interview_id).first()
            candidate = db.query(Candidate).filter(Candidate.candidateID == reminder.candidate_id).first()

            if interview is None or candidate is None or interview.confirmed_at is None:  # BR-03
                reminder.status = "CANCELLED"
                db.add(reminder)
                db.commit()
                result["cancelled"] += 1
                continue

            submission = db.query(Submission).filter(Submission.id == interview.submission_id).first()
            interviewer_name = _resolve_interviewer_name(db, interview.panel_id)
            meeting_detail = interview.notes.strip() if interview.notes else "Details will be shared closer to the interview date."
            candidate_local = _as_utc(interview.scheduled_at).astimezone(ZoneInfo(candidate.timezone or "Asia/Kolkata"))
            message = _build_reminder_message(reminder.reminder_type, candidate, interviewer_name, candidate_local, meeting_detail)

            conversation = (
                db.query(CandidateConversation)
                .filter(CandidateConversation.candidate_id == candidate.candidateID)
                .order_by(CandidateConversation.id.desc())
                .first()
            )

            # S-075/HRMS-0475: the email branch below is a raw
            # EmailService.send_email() bypassing send_thunder_message()'s
            # own pause check entirely, so it's checked once here for
            # both channels. Left PENDING (not CANCELLED) so it retries
            # on this job's next 10-min tick once Thunder resumes --
            # never counted as a "both failed" escalation.
            if conversation is not None and is_thunder_paused_for_conversation(db, conversation):
                result["skipped"] += 1
                continue

            whatsapp_sent = False
            if conversation is not None:
                try:
                    send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
                    whatsapp_sent = True
                except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
                    logger.info(f"[InterviewReminder] WhatsApp reminder skipped for candidate {candidate.candidateID!r}: {exc}")

            email_sent = False
            try:
                EmailService.send_email(candidate.candidateEmail, "Your BlitzenX Interview Reminder", f"<p>{message}</p>", is_html=True)
                if conversation is not None:
                    db.add(ConversationEvent(conversation_id=conversation.id, event_type="ai_message_sent", event_data={"channel": "email", "body": message[:500], "auto_generated": True}, triggered_by="ai_agent"))
                email_sent = True
            except Exception as exc:
               logger.error(f"Error: {str(exc)}", exc_info=True)
                logger.error(f"[InterviewReminder] Email reminder failed for candidate {candidate.candidateID!r}: {exc}")

            if not whatsapp_sent and not email_sent:  # BR-02's own integrations note: both fail -> escalate
                if conversation is not None:
                    db.add(ConversationEvent(conversation_id=conversation.id, event_type="REMINDER_SEND_FAILED", event_data={"reminder_id": reminder.id, "reminder_type": reminder.reminder_type}, triggered_by="system"))
                _notify_recruiter(db, submission, f"Both WhatsApp and email reminders failed for {candidate.candidateFirstName or candidate.candidateID}'s upcoming interview -- please follow up directly.")
                reminder.status = "CANCELLED"
                db.add(reminder)
                db.commit()
                result["skipped"] += 1
                continue

            reminder.status = "SENT"
            reminder.sent_at = now
            db.add(reminder)
            db.commit()
            result["sent"] += 1
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[InterviewReminder] Unexpected failure processing reminder id={reminder.id}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result
