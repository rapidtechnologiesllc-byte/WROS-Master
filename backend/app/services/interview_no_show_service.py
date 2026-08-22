"""
S-052/HRMS-0452 -- Interview No-Show Handling.

Real architecture adaptations:
- No `interviews.status` CONFIRMED/NO_SHOW_CHECK_IN_SENT/NO_SHOW/
  NO_SHOW_NO_RESPONSE literal values exist -- `SubmissionInterview`
  gained 4 new nullable timestamp columns instead (see its own model
  docstring), same timestamp-presence convention `confirmed_at`/
  `superseded_at` already established: no_show_check_in_at,
  no_show_confirmed_at, no_show_reschedule_offer_sent_at,
  no_show_no_response_at. "status stays CONFIRMED" simply means none
  of these get set.
- "Check if candidate sent ANY inbound message after scheduled_at_utc"
  maps onto a real `ConversationEvent` query (`event_type=
  'candidate_reply'`, `created_at > scheduled_at`) on the candidate's
  active conversation -- same mapping every S-041-051 story already
  uses, not a fictional `conversation_messages` table.
- Step 4's "route to HRMS-0451 reschedule flow" is a real, direct call
  to `interview_reschedule_service.start_reschedule()` -- this story's
  own spec explicitly says to route there, so this is in-scope reuse,
  not a unilateral wiring decision. `start_reschedule()` resolves "the
  candidate's current (non-superseded, confirmed) interview" itself
  (see its own docstring) -- a no-show'd interview is still
  `confirmed_at`-set and non-superseded, so it's found correctly with
  no extra plumbing needed.
- BR-02 ("recruiter makes the final decision, Thunder does not
  auto-disqualify") is honored by construction: nothing in this module
  ever writes to `Submission.status`, `outcome`, or any disqualification
  field. `no_show_no_response_at` is a pure observability marker for a
  recruiter to act on, never an automated rejection.
- Interviewer notification uses direct `EmailService.send_email()` per
  the spec's own literal "notify interviewer via email" integration
  row -- there's no gated interviewer-facing send path in this
  codebase (interviewer isn't a "candidate," so
  `thunder_service.send_thunder_message()` doesn't apply), same
  "direct EmailService call when no gated path exists" convention this
  whole round has used for every non-candidate email.
- Both the check-in message (Step 2, spec explicitly says "via
  WhatsApp... simultaneously via email as backup") and the reschedule
  offer (Step 4, spec doesn't repeat the dual-channel instruction --
  sent WhatsApp-only here, a deliberate minimal-deviation reading of
  the literal text rather than assuming BR-02/S-050's dual-channel
  rule silently carries over) reuse `thunder_service.send_thunder_message()`
  (R-08/consent/debounce still real, hard invariants).
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
from app.models.submission import Submission
from app.models.user import Users
from app.services.email_service import EmailService
from app.services.notification_service import send_notification
from app.services.thunder_pause_service import is_thunder_paused_for_conversation
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message

CHECK_IN_MINUTES = 15  # Step 1
NO_SHOW_CONFIRM_MINUTES = 30  # BR-01 -- total minutes since scheduled_at_utc
DETECTION_WINDOW_MAX_MINUTES = 90  # Step 1's own upper bound, avoids re-scanning ancient rows forever
RESCHEDULE_OFFER_DELAY_HOURS = 2  # Step 4
RESCHEDULE_OFFER_TIMEOUT_HOURS = 48  # Step 4
JOB_BATCH_SIZE = 100


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def _active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )


def _has_replied_since(db: Session, conversation_id: int, since: datetime) -> bool:
    reply = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > since)
        .first()
    )
    return reply is not None


def _resolve_interviewer_user(db: Session, panel_id: Optional[str]) -> Optional[Users]:
    if not panel_id:
        return None
    panel = db.query(DemandInterviewPanel).filter(DemandInterviewPanel.id == panel_id).first()
    if panel is None:
        return None
    employee = db.query(Employee).filter(Employee.id == panel.employee_id).first()
    if employee is None or not employee.wros_user_id:
        return None
    return db.query(Users).filter(Users.UserID == employee.wros_user_id).first()


def _interviewer_name(db: Session, panel_id: Optional[str]) -> str:
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
        logger.warning(f"[InterviewNoShow] Failed to notify recruiter: {exc}")


def _send_thunder_message_best_effort(db: Session, conversation: Optional[CandidateConversation], candidate: Candidate, message: str) -> bool:
    if conversation is None:
        return False
    try:
        send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
        return True
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
        logger.info(f"[InterviewNoShow] WhatsApp message skipped for candidate {candidate.candidateID!r}: {exc}")
        return False


def run_no_show_detection_job(db: Session) -> Dict:
    """Steps 1 + 3, combined -- runs every 5 min. Never lets one bad
    row abort the batch."""
    result = {"processed": 0, "check_in_sent": 0, "no_show_confirmed": 0, "skipped": 0}
    now = datetime.now(dt_timezone.utc)

    # Step 1: interviews 15-90 min past start, no check-in sent yet.
    pending_check_in = (
        db.query(SubmissionInterview)
        .filter(
            SubmissionInterview.confirmed_at != None, SubmissionInterview.superseded_at == None,  # noqa: E711
            SubmissionInterview.no_show_check_in_at == None, SubmissionInterview.scheduled_at != None,
        )
        .limit(JOB_BATCH_SIZE)
        .all()
    )
    for interview in pending_check_in:
        result["processed"] += 1
        try:
            scheduled_utc = _as_utc(interview.scheduled_at)
            minutes_elapsed = (now - scheduled_utc).total_seconds() / 60
            if minutes_elapsed < CHECK_IN_MINUTES or minutes_elapsed > DETECTION_WINDOW_MAX_MINUTES:
                result["skipped"] += 1
                continue

            candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
            conversation = _active_conversation(db, interview.candidate_id)
            if candidate is None:
                result["skipped"] += 1
                continue

            if conversation is not None and _has_replied_since(db, conversation.id, scheduled_utc):
                result["skipped"] += 1
                continue  # AC-3: candidate already checked in -- stays CONFIRMED

            # S-075/HRMS-0475: the email check-in below is a raw
            # EmailService.send_email() bypassing send_thunder_message()'s
            # own pause check. no_show_check_in_at is left unset (not the
            # whatsapp-only _send_thunder_message_best_effort's job to
            # cover the email leg too) so this candidate is re-evaluated
            # on the job's next 5-min tick once Thunder resumes.
            if conversation is not None and is_thunder_paused_for_conversation(db, conversation):
                result["skipped"] += 1
                continue

            interviewer_name = _interviewer_name(db, interview.panel_id)
            local_time = scheduled_utc.astimezone(ZoneInfo(candidate.timezone or "Asia/Kolkata"))
            message = (
                f"Hi {candidate.candidateFirstName or 'there'}! Your interview with {interviewer_name} was scheduled "
                f"for {local_time.strftime('%I:%M %p %Z')}. Are you still joining? Please let us know and we can "
                f"hold a few more minutes for you."
            )
            _send_thunder_message_best_effort(db, conversation, candidate, message)
            try:
                EmailService.send_email(candidate.candidateEmail, "Are you still joining your BlitzenX interview?", f"<p>{message}</p>", is_html=True)
                if conversation is not None:
                    db.add(ConversationEvent(conversation_id=conversation.id, event_type="ai_message_sent", event_data={"channel": "email", "body": message[:500], "auto_generated": True, "message_type": "NO_SHOW_CHECK_IN"}, triggered_by="ai_agent"))
            except Exception as exc:
                logger.error(f"[InterviewNoShow] Check-in email failed for candidate {candidate.candidateID!r}: {exc}")

            interview.no_show_check_in_at = now.replace(tzinfo=None)
            db.add(interview)
            db.commit()
            result["check_in_sent"] += 1
        except Exception as exc:
            logger.error(f"[InterviewNoShow] Failed processing check-in for interview {interview.id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    # Step 3: check-in already sent, 30 total min elapsed, still no reply.
    pending_confirm = (
        db.query(SubmissionInterview)
        .filter(
            SubmissionInterview.no_show_check_in_at != None, SubmissionInterview.no_show_confirmed_at == None,  # noqa: E711
            SubmissionInterview.superseded_at == None,
        )
        .limit(JOB_BATCH_SIZE)
        .all()
    )
    for interview in pending_confirm:
        result["processed"] += 1
        try:
            scheduled_utc = _as_utc(interview.scheduled_at)
            minutes_elapsed = (now - scheduled_utc).total_seconds() / 60
            if minutes_elapsed < NO_SHOW_CONFIRM_MINUTES:
                result["skipped"] += 1
                continue

            candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
            conversation = _active_conversation(db, interview.candidate_id)
            if candidate is None:
                result["skipped"] += 1
                continue

            if conversation is not None and _has_replied_since(db, conversation.id, scheduled_utc):
                result["skipped"] += 1
                continue  # candidate checked in between the check-in send and now

            interview.no_show_confirmed_at = now.replace(tzinfo=None)
            db.add(interview)
            if conversation is not None:
                db.add(ConversationEvent(
                    conversation_id=conversation.id, event_type="INTERVIEW_NO_SHOW",
                    event_data={"interview_id": interview.id, "candidate_id": candidate.candidateID, "scheduled_at_utc": scheduled_utc.isoformat()}, triggered_by="system",
                ))
            db.commit()

            if conversation is not None:
                # S-062/HRMS-0462: real intervention-queue wiring.
                from app.services.intervention_queue_service import PRIORITY_HIGH, add_to_queue
                add_to_queue(db, candidate.candidateID, conversation.tenant_id, "NO_SHOW", f"No-show: {interview.level} interview at {scheduled_utc.strftime('%b %d, %H:%M UTC')}", PRIORITY_HIGH)

            submission = db.query(Submission).filter(Submission.id == interview.submission_id).first()
            local_time = scheduled_utc.astimezone(ZoneInfo(candidate.timezone or "Asia/Kolkata"))
            candidate_name = candidate.candidateFirstName or candidate.candidateID
            _notify_recruiter(db, submission, f"{candidate_name} did not join their {interview.level} interview at {local_time.strftime('%I:%M %p %Z, %b %d')}. Please decide next steps.")

            interviewer_user = _resolve_interviewer_user(db, interview.panel_id)
            if interviewer_user is not None:
                try:
                    EmailService.send_email(
                        interviewer_user.UserEmail, "Candidate did not join the interview",
                        "<p>The candidate did not join. We are following up with them now. We will reschedule if appropriate.</p>", is_html=True,
                    )
                except Exception as exc:
                    logger.error(f"[InterviewNoShow] Interviewer notification email failed: {exc}")

            result["no_show_confirmed"] += 1
        except Exception as exc:
            logger.error(f"[InterviewNoShow] Failed confirming no-show for interview {interview.id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result


def run_no_show_followup_job(db: Session) -> Dict:
    """Step 4 -- the reschedule-offer follow-through. Never lets one
    bad row abort the batch."""
    result = {"processed": 0, "offer_sent": 0, "rescheduled": 0, "no_response": 0, "skipped": 0}
    now = datetime.now(dt_timezone.utc)

    # (a) send the reschedule offer, 2h after no-show confirmed.
    pending_offer = (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.no_show_confirmed_at != None, SubmissionInterview.no_show_reschedule_offer_sent_at == None)  # noqa: E711
        .limit(JOB_BATCH_SIZE)
        .all()
    )
    for interview in pending_offer:
        result["processed"] += 1
        try:
            confirmed_utc = _as_utc(interview.no_show_confirmed_at)
            if (now - confirmed_utc) < timedelta(hours=RESCHEDULE_OFFER_DELAY_HOURS):
                result["skipped"] += 1
                continue

            candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
            conversation = _active_conversation(db, interview.candidate_id)
            if candidate is None:
                result["skipped"] += 1
                continue

            message = (
                "We missed you today! If something came up, we completely understand. Would you like to "
                "reschedule your interview? Please let us know and we can find another time."
            )
            _send_thunder_message_best_effort(db, conversation, candidate, message)

            interview.no_show_reschedule_offer_sent_at = now.replace(tzinfo=None)
            db.add(interview)
            db.commit()
            result["offer_sent"] += 1
        except Exception as exc:
            logger.error(f"[InterviewNoShow] Failed sending reschedule offer for interview {interview.id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    # (b)/(c) offer already sent -- either the candidate replied (route to
    # reschedule) or 48h passed with no reply (mark NO_SHOW_NO_RESPONSE).
    pending_response = (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.no_show_reschedule_offer_sent_at != None, SubmissionInterview.no_show_no_response_at == None, SubmissionInterview.superseded_at == None)  # noqa: E711
        .limit(JOB_BATCH_SIZE)
        .all()
    )
    for interview in pending_response:
        result["processed"] += 1
        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
            conversation = _active_conversation(db, interview.candidate_id)
            if candidate is None or conversation is None:
                result["skipped"] += 1
                continue

            offer_sent_utc = _as_utc(interview.no_show_reschedule_offer_sent_at)
            if _has_replied_since(db, conversation.id, offer_sent_utc):
                from app.services.interview_reschedule_service import start_reschedule
                start_reschedule(db, candidate, conversation, conversation.tenant_id)
                result["rescheduled"] += 1
                continue

            if (now - offer_sent_utc) >= timedelta(hours=RESCHEDULE_OFFER_TIMEOUT_HOURS):
                interview.no_show_no_response_at = now.replace(tzinfo=None)  # BR-02: observability only, never auto-disqualifies
                db.add(interview)
                db.commit()
                result["no_response"] += 1
            else:
                result["skipped"] += 1
        except Exception as exc:
            logger.error(f"[InterviewNoShow] Failed processing reschedule-offer follow-up for interview {interview.id!r}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result
