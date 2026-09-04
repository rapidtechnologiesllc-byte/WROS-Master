"""
import logging
S-051/HRMS-0451 -- Interview Reschedule Workflow.

Real architecture adaptations:
- Ties together S-047/S-048/S-049/S-050 for real -- this story's own
  job IS "run the scheduling pipeline again," so calling those
  previously-standalone functions from here is squarely in-scope, not
  a unilateral wiring decision the way it would have been for any of
  those stories to wire themselves into a live loop on their own.
  `start_reschedule()` (Step 2) and
  `complete_reschedule_match_and_confirm()` (Steps 3-4) are themselves
  still NOT wired into a live trigger -- same posture the whole chain
  has taken -- but everything they call (S-047's
  `parse_availability_response`, S-048's `attempt_calendar_match`,
  S-049's `confirm_interview`, S-050's
  `schedule_reminders_for_interview`/`cancel_pending_reminders_for_interview`)
  is called directly, for real.
- No `INTERVIEW_SCHEDULED` conversation state, no `interviews.status`
  RESCHEDULING/RESCHEDULED values (same fictional enum every S-041-050
  story has already flagged) -- "is this candidate's interview
  currently being rescheduled, and for which old interview" is derived
  from real `ConversationEvent` history instead of a dedicated column:
  a `RESCHEDULE_STARTED` event with no later `INTERVIEW_RESCHEDULED` or
  `RESCHEDULE_LIMIT_ESCALATED` event for the same old interview means
  the reschedule is still in progress. Same "derive workflow state from
  event history, don't invent a status column" convention
  `no_response_detection_service`/`ghosting_detection_service` already
  established.
- BR-03's real constraint conflict (a second `SubmissionInterview` row
  for the same submission+level) is resolved by the new partial unique
  index added to `SubmissionInterview` itself this story (see that
  model's own docstring) -- `superseded_at` is set on the OLD interview
  in the exact same commit as the NEW interview's creation (only on an
  actual match; see `calendar_matching_service.attempt_calendar_match()`'s
  own `supersede_interview_id` docstring), so a stalled/failed
  reschedule attempt never orphans the candidate's still-valid old
  interview.
- BR-02's Outlook cancellation is a real, injectable Graph `DELETE
  /events/{id}` call (same minimal-call pattern S-048/S-049 already
  established) -- best-effort: if it fails, the reschedule flow
  continues anyway (per the spec's own integrations table: "if delete
  fails: log. Create new event anyway. Recruiter notified to manually
  decline old.") rather than blocking the candidate's reschedule on an
  Outlook API hiccup.
- Old `interview_reminders` are cancelled via S-050's own real
  `cancel_pending_reminders_for_interview()` -- not reimplemented.
- BR-01's escalation reuses `conversation_state_service.escalate()`/
  `pause_for_recruiter_queue()` directly (the same real primitives
  S-035's `escalation_detection_service.execute_escalation()` is built
  from) rather than calling `execute_escalation()` itself, since this
  story's own spec prescribes a different, specific exit message --
  the ORDER of operations (message first, then state transition, then
  notify) still matches that established precedent.
- A known, honest gap: cancelling the old Outlook event at Step 2 does
  NOT retroactively clear that interview row's own `confirmed_at`/
  `scheduled_via_graph_event_id` -- if a reschedule stalls forever with
  no new slots ever provided, the old interview row still looks
  "confirmed" in this codebase's own data even though its real-world
  calendar invite is gone. No literal 'RESCHEDULING' status exists to
  record that in-between state; flagged rather than silently
  papered over.
"""
from datetime import datetime
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.submission import Submission
from app.models.user import Users
from app.services import conversation_state_service
from app.services.calendar_matching_service import attempt_calendar_match
from app.services.interview_confirmation_service import confirm_interview
from app.services.interview_reminder_service import cancel_pending_reminders_for_interview, schedule_reminders_for_interview
from app.services.notification_service import send_notification
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message

MAX_RESCHEDULES = 2  # BR-01
RESCHEDULE_ACK_MESSAGE = (
    "Of course, no problem! Let me check available times. Could you please share 2-3 alternative "
    "time slots that work for you over the next 5 working days?"
)
ESCALATION_MESSAGE = "I have reached out to our recruiting team to assist with your scheduling. Someone will be in touch with you shortly."

GraphDeleteEventCall = Callable[[str, str], None]

def _default_graph_delete_event_call(organizer_email: str, event_id: str) -> None:
    import requests
    from app.core.graph_auth import get_graph_token

    access_token = get_graph_token()
    endpoint = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events/{event_id}"
    resp = requests.delete(endpoint, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()

def _find_current_interview(db: Session, candidate_id: str) -> Optional[SubmissionInterview]:
    """The candidate's current (non-superseded), confirmed interview --
    the real substitute for a fictional INTERVIEW_SCHEDULED conversation
    state."""
    return (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.candidate_id == candidate_id, SubmissionInterview.superseded_at == None, SubmissionInterview.confirmed_at != None)  # noqa: E711
        .order_by(SubmissionInterview.created_at.desc())
        .first()
    )

def _find_active_reschedule_interview_id(db: Session, conversation_id: int) -> Optional[str]:
    """See module docstring: derives 'is a reschedule mid-flight, and
    for which old interview' from ConversationEvent history rather than
    a dedicated status column."""
    started_events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "RESCHEDULE_STARTED")
        .order_by(ConversationEvent.created_at.desc())
        .all()
    )
    for event in started_events:
        old_interview_id = (event.event_data or {}).get("old_interview_id")
        if not old_interview_id:
            continue
        resolved = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type.in_(["INTERVIEW_RESCHEDULED", "RESCHEDULE_LIMIT_ESCALATED"]), ConversationEvent.created_at > event.created_at)
            .first()
        )
        if resolved is None:
            return old_interview_id
    return None

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
        logger.warning(f"[InterviewReschedule] Failed to notify recruiter: {exc}")

def _escalate_for_scheduling(db: Session, candidate: Candidate, conversation: CandidateConversation, interview: SubmissionInterview) -> Dict:
    """Step 5/BR-01."""
    try:
        send_thunder_message(db, conversation, candidate, ESCALATION_MESSAGE, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
        logger.info(f"[InterviewReschedule] Escalation message skipped for candidate {candidate.candidateID!r}: {exc}")

    conversation_state_service.escalate(db, conversation, reason="3+ interview reschedule requests", triggered_by="ai_agent")
    conversation_state_service.pause_for_recruiter_queue(db, conversation, reason="3+ interview reschedule requests")
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="RESCHEDULE_LIMIT_ESCALATED",
        event_data={"interview_id": interview.id, "reschedule_count": interview.reschedule_count}, triggered_by="system",
    ))
    db.commit()

    submission = db.query(Submission).filter(Submission.id == interview.submission_id).first()
    _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} has requested 3+ reschedules. Please handle scheduling directly.")

    return {"outcome": "escalated", "message": ESCALATION_MESSAGE}

def start_reschedule(
    db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str, *, graph_delete_event_call: Optional[GraphDeleteEventCall] = None,
) -> Dict:
    """Step 2. Never raises. Returns one of:
      {"outcome": "no_current_interview"}
      {"outcome": "escalated", "message": ...}
      {"outcome": "reschedule_started", "message": ...}
    """
    try:
        interview = _find_current_interview(db, candidate.candidateID)
        if interview is None:
            return {"outcome": "no_current_interview"}

        if interview.reschedule_count >= MAX_RESCHEDULES:  # BR-01
            return _escalate_for_scheduling(db, candidate, conversation, interview)

        # BR-02: cancel the old Outlook event -- best-effort, never blocks the flow.
        if interview.scheduled_via_graph_event_id:
            interviewer_user = _resolve_interviewer_user(db, interview.panel_id)
            if interviewer_user is not None:
                call = graph_delete_event_call or _default_graph_delete_event_call
                try:
                    call(interviewer_user.UserEmail, interview.scheduled_via_graph_event_id)
                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(f"[InterviewReschedule] Failed to cancel old Outlook event for interview {interview.id!r}: {exc}")
                    submission = db.query(Submission).filter(Submission.id == interview.submission_id).first()
                    _notify_recruiter(db, submission, f"Could not cancel the old Outlook invite for {candidate.candidateFirstName or candidate.candidateID}'s interview -- please decline it manually.")

        cancel_pending_reminders_for_interview(db, interview.id)  # reuse S-050 directly

        # Step 3's own first bullet -- fresh availability collection starts clean.
        db.query(CandidateAvailabilitySlot).filter(
            CandidateAvailabilitySlot.tenant_id == tenant_id, CandidateAvailabilitySlot.candidate_id == candidate.candidateID,
        ).delete(synchronize_session=False)

        db.add(ConversationEvent(conversation_id=conversation.id, event_type="RESCHEDULE_STARTED", event_data={"old_interview_id": interview.id}, triggered_by="candidate"))
        db.commit()

        return {"outcome": "reschedule_started", "message": RESCHEDULE_ACK_MESSAGE}
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[InterviewReschedule] Unexpected failure starting reschedule for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "reschedule_failed"}

def complete_reschedule_match_and_confirm(
    db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str, *, graph_call=None, graph_create_event_call=None,
) -> Dict:
    """Steps 3-4. Called once >=2 new valid slots exist -- i.e. right
    after S-047's parse_availability_response() returns
    outcome="slots_sufficient" during an active reschedule. Never
    raises. Returns one of:
      {"outcome": "no_active_reschedule"}
      {"outcome": <any attempt_calendar_match outcome other than "matched">, ...}
      {"outcome": "matched_and_confirmed", "old_interview_id": ..., "new_interview_id": ..., "confirm_result": {...}, "reminders_created": [...]}
    """
    try:
        old_interview_id = _find_active_reschedule_interview_id(db, conversation.id)
        if old_interview_id is None:
            return {"outcome": "no_active_reschedule"}

        old_interview = db.query(SubmissionInterview).filter(SubmissionInterview.id == old_interview_id).first()
        if old_interview is None:
            return {"outcome": "no_active_reschedule"}

        match_result = attempt_calendar_match(
            db, candidate, conversation, tenant_id, level=old_interview.level,
            reschedule_count=old_interview.reschedule_count + 1, rescheduled_from_interview_id=old_interview.id,
            supersede_interview_id=old_interview.id, graph_call=graph_call,
        )
        if match_result.get("outcome") != "matched":
            return match_result  # no_match / calendar_check_failed / etc -- pass through honestly, old interview untouched

        new_interview_id = match_result["interview_id"]
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="INTERVIEW_RESCHEDULED",
            event_data={"old_interview_id": old_interview.id, "new_interview_id": new_interview_id, "reschedule_count": old_interview.reschedule_count + 1}, triggered_by="system",
        ))
        db.commit()

        confirm_result = confirm_interview(db, new_interview_id, candidate, conversation, graph_create_event_call=graph_create_event_call)
        reminder_result = schedule_reminders_for_interview(db, new_interview_id)

        return {
            "outcome": "matched_and_confirmed", "old_interview_id": old_interview.id, "new_interview_id": new_interview_id,
            "confirm_result": confirm_result, "reminders_created": reminder_result.get("reminders_created", []),
        }
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[InterviewReschedule] Unexpected failure completing reschedule for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "reschedule_failed"}
