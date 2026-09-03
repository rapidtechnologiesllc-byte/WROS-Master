"""
import logging
S-067/HRMS-0467 -- Onboarding Agent.

Real architecture adaptation: built standalone (per Avinash's explicit
direction, 2026-08-04), not dispatched by a fictional Supervisor
per-candidate sub-agent loop -- same pattern every other agent this
session uses (document_collection_service, joining_readiness_service,
interview_reminder_service): its own scheduled job, re-evaluating
real DB state every cycle.

No system_configuration table -- JOINING_INSTRUCTIONS_D7_TEMPLATE and
the other message bodies below are real module constants (BA-approved
placeholder wording, flagged not yet BA-reviewed, same posture as
S-029's synonym library / S-055's DEFAULT_FAQ_CONTENT).

"PREBOARDING" state = OfferLetter.offer_status == "Accepted", same
real substitute S-057/S-058/S-059 already established -- no fictional
conversation.status=PREBOARDING value exists.

BR-02 (omit "please send documents" if already complete) implemented
by checking whether any PENDING PreboardingDocument row remains for
this offer at D-7 send time.

See preboarding_touchpoint.py's own module docstring for why D+1 is
scheduled only at completion-detection time, not upfront, and why its
presence is this module's own idempotency guard for BR-03 (never
notifies HR / emits onboarding.complete twice).
"""
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.employee import Employee
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.preboarding_touchpoint import PreboardingTouchpoint
from app.models.submission import Submission
from app.models.user import Users
from app.services.email_service import EmailService
from app.services.notification_service import send_notification
from app.services.thunder_service import (
    ConsentNotGiven,
    ConversationOwnedByHuman,
    DuplicateMessageSuppressed,
    ThunderPausedError,
    send_thunder_message,
)

TOUCHPOINT_OFFSETS_DAYS = {"D7": 7, "D3": 3, "D1": 1}
SEND_HOUR_UTC = 9  # module constant -- same fixed-hour simplicity level as other reminder jobs

JOINING_INSTRUCTIONS_D7_TEMPLATE = (
    "Hi {name}! You're joining BlitzenX on {joining_date}. Here's what you need to know: "
    "reporting details and your first-day schedule will be shared closer to your start date, "
    "your point of contact is our HR team, and IT will reach out about your system setup. "
    "{documents_line}"
    "Let us know if you have any questions!"
)
DOCUMENTS_STILL_PENDING_LINE = "A quick reminder -- we're still waiting on a few documents from you; our HR team will follow up on specifics. "
D3_CHECKLIST_MESSAGE = (
    "Hi {name}! Just 3 days until your first day at BlitzenX on {joining_date}. "
    "A quick checklist: keep an eye out for your final joining instructions, make sure your documents are in, "
    "and get a good night's sleep before the big day!"
)
D1_MESSAGE = "Hi {name}! Your first day at BlitzenX is tomorrow! We are so excited to have you join! See you tomorrow!"
D_PLUS_1_MESSAGE = "Hi {name}! Welcome to BlitzenX -- hope your first day went great! Our HR team is here if you need anything."

def _candidate_display_name(candidate: Candidate) -> str:
    return candidate.candidateFirstName or candidate.candidateEmail

def _relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return db.query(Submission).filter(Submission.candidate_id == candidate_id).order_by(Submission.id.desc()).first()

def _notify_recruiter(db: Session, submission: Optional[Submission], message: str) -> None:
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier="P2", channel_preference="IN_APP", message=message)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingAgent] Failed to notify recruiter: {exc}")

def schedule_onboarding_touchpoints(db: Session, candidate: Candidate, offer: OfferLetter, tenant_id: str) -> List[PreboardingTouchpoint]:
    """BR-01: only ever called when entering PREBOARDING (offer
    accepted) -- wired into offer_decision_service._handle_acceptance(),
    the same real trigger S-057's start_document_collection() uses."""
    if offer.joining_date is None:
        logger.warning(f"[OnboardingAgent] Offer {offer.id!r} has no joining_date -- cannot schedule touchpoints.")
        return []

    if db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer.id).count():
        return []  # already scheduled -- idempotent

    created = []
    for touchpoint_type, offset_days in TOUCHPOINT_OFFSETS_DAYS.items():
        scheduled_date = offer.joining_date - timedelta(days=offset_days)
        scheduled_at = datetime.combine(scheduled_date, dt_time(SEND_HOUR_UTC, 0))
        row = PreboardingTouchpoint(
            tenant_id=tenant_id, candidate_id=candidate.candidateID, offer_id=offer.id,
            touchpoint_type=touchpoint_type, scheduled_at=scheduled_at, status="PENDING",
        )
        db.add(row)
        created.append(row)
    db.commit()
    return created

def cancel_pending_touchpoints_for_candidate(db: Session, candidate_id: str) -> int:
    """BR-01: withdrawal during PREBOARDING cancels all pending
    touchpoints -- wired into offer_decision_service._handle_decline()."""
    rows = db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.candidate_id == candidate_id, PreboardingTouchpoint.status == "PENDING").all()
    for row in rows:
        row.status = "CANCELLED"
        db.add(row)
    if rows:
        db.commit()
    return len(rows)

def _active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate_id).order_by(CandidateConversation.id.desc()).first()

def _send_touchpoint_message(db: Session, conversation: CandidateConversation, candidate: Candidate, message: str, email_subject: str) -> bool:
    """Sends via BOTH whatsapp and email independently, same pattern
    interview_reminder_service established -- either succeeding counts
    as delivered."""
    whatsapp_sent = False
    try:
        send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
        whatsapp_sent = True
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
        logger.info(f"[OnboardingAgent] WhatsApp touchpoint skipped for candidate {candidate.candidateID!r}: {exc}")

    email_sent = False
    try:
        EmailService.send_email(candidate.candidateEmail, email_subject, f"<p>{message}</p>", is_html=True)
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="ai_message_sent",
            event_data={"channel": "email", "body": message[:500], "auto_generated": True, "message_type": "ONBOARDING_TOUCHPOINT"},
            triggered_by="ai_agent",
        ))
        db.commit()
        email_sent = True
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingAgent] Email touchpoint failed for candidate {candidate.candidateID!r}: {exc}")

    return whatsapp_sent or email_sent

def _build_message(touchpoint_type: str, candidate: Candidate, offer: OfferLetter, db: Session) -> str:
    name = _candidate_display_name(candidate)
    joining_date = offer.joining_date.strftime("%B %d, %Y") if offer.joining_date else "your start date"

    if touchpoint_type == "D7":
        docs_pending = db.query(PreboardingDocument).filter(PreboardingDocument.offer_id == offer.id, PreboardingDocument.status == "PENDING").first() is not None
        documents_line = DOCUMENTS_STILL_PENDING_LINE if docs_pending else ""  # BR-02
        return JOINING_INSTRUCTIONS_D7_TEMPLATE.format(name=name, joining_date=joining_date, documents_line=documents_line)
    if touchpoint_type == "D3":
        return D3_CHECKLIST_MESSAGE.format(name=name, joining_date=joining_date)
    if touchpoint_type == "D1":
        return D1_MESSAGE.format(name=name)
    return D_PLUS_1_MESSAGE.format(name=name)  # D_PLUS_1

def check_onboarding_completion(db: Session, candidate_id: str, offer_id: int, tenant_id: str) -> bool:
    """Step 4. Idempotent -- see preboarding_touchpoint.py's own module
    docstring on why the D_PLUS_1 row's presence is the real
    completion guard."""
    if db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer_id, PreboardingTouchpoint.touchpoint_type == "D_PLUS_1").first():
        return False

    if db.query(PreboardingDocument).filter(PreboardingDocument.offer_id == offer_id, PreboardingDocument.status == "PENDING").first():
        return False

    core_touchpoints = db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer_id, PreboardingTouchpoint.touchpoint_type.in_(("D7", "D3", "D1"))).all()
    if not core_touchpoints or any(t.status == "PENDING" for t in core_touchpoints):
        return False

    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if offer is None or candidate is None:
        return False

    d_plus_1_at = (
        datetime.combine(offer.joining_date + timedelta(days=1), dt_time(SEND_HOUR_UTC, 0))
        if offer.joining_date else datetime.utcnow() + timedelta(days=1)
    )
    db.add(PreboardingTouchpoint(tenant_id=tenant_id, candidate_id=candidate_id, offer_id=offer_id, touchpoint_type="D_PLUS_1", scheduled_at=d_plus_1_at, status="PENDING"))
    db.commit()

    documents_received = [d.document_type for d in db.query(PreboardingDocument).filter(PreboardingDocument.offer_id == offer_id, PreboardingDocument.status == "RECEIVED").all()]
    touchpoints_completed = [t.touchpoint_type for t in core_touchpoints]

    readiness_score = None
    try:
        from app.services.joining_readiness_service import calculate_joining_readiness
        readiness = calculate_joining_readiness(db, candidate_id, offer_id, tenant_id)
        readiness_score = readiness.get("readiness_score") if isinstance(readiness, dict) else None
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingAgent] Could not compute joining readiness for candidate {candidate_id!r}: {exc}")

    submission = _relevant_submission(db, candidate_id)
    joining_date_str = offer.joining_date.strftime("%b %d, %Y") if offer.joining_date else "their start date"
    _notify_recruiter(db, submission, f"{_candidate_display_name(candidate)} is fully prepared for joining on {joining_date_str}. All documents received. Preboarding complete.")

    try:
        from app.services.event_emitter_service import emit
        emit(
            db, "onboarding.complete",
            {
                "candidate_id": candidate_id, "tenant_id": tenant_id,
                "joining_date": offer.joining_date.isoformat() if offer.joining_date else None,
                "documents_received": documents_received, "touchpoints_completed": touchpoints_completed,
                "joining_readiness_score": readiness_score,
            },
            tenant_id, candidate_id,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingAgent] Failed to emit onboarding.complete for candidate {candidate_id!r}: {exc}")

    return True

def run_onboarding_touchpoint_job(db: Session) -> Dict:
    """Standalone scheduled job (every 6h, matching document_reminder_
    job's cadence) -- own dispatch loop, per Avinash's explicit
    direction not to depend on S-066's SupervisorAgent for this."""
    result = {"processed": 0, "sent": 0, "skipped": 0, "cancelled": 0, "completions_detected": 0}
    now = datetime.utcnow()

    due = db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.status == "PENDING", PreboardingTouchpoint.scheduled_at <= now).all()
    for touchpoint in due:
        result["processed"] += 1
        try:
            offer = db.query(OfferLetter).filter(OfferLetter.id == touchpoint.offer_id).first()
            candidate = db.query(Candidate).filter(Candidate.candidateID == touchpoint.candidate_id).first()
            if offer is None or candidate is None or offer.offer_status != "Accepted":
                touchpoint.status = "CANCELLED"
                db.add(touchpoint)
                db.commit()
                result["cancelled"] += 1
                continue

            if touchpoint.touchpoint_type == "D_PLUS_1":
                if db.query(Employee).filter(Employee.candidate_id == touchpoint.candidate_id).first() is None:
                    result["skipped"] += 1  # Step 1: "if employee record created" -- retry next cycle
                    continue

            conversation = _active_conversation(db, touchpoint.candidate_id)
            if conversation is None:
                result["skipped"] += 1
                continue

            message = _build_message(touchpoint.touchpoint_type, candidate, offer, db)
            subject = (
                f"{_candidate_display_name(candidate)} — Joining Instructions for {offer.joining_date.strftime('%b %d, %Y')}"
                if touchpoint.touchpoint_type == "D7" and offer.joining_date else "BlitzenX Onboarding"
            )
            if _send_touchpoint_message(db, conversation, candidate, message, subject):
                touchpoint.status = "SENT"
                touchpoint.sent_at = now
                db.add(touchpoint)
                db.commit()
                result["sent"] += 1
            else:
                result["skipped"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[OnboardingAgent] Failed processing touchpoint id={touchpoint.id}: {exc}")
            db.rollback()
            result["skipped"] += 1

    offer_ids = {row[0] for row in db.query(PreboardingTouchpoint.offer_id).filter(PreboardingTouchpoint.touchpoint_type.in_(("D7", "D3", "D1"))).distinct().all()}
    for offer_id in offer_ids:
        touchpoint = db.query(PreboardingTouchpoint).filter(PreboardingTouchpoint.offer_id == offer_id).first()
        if touchpoint is None:
            continue
        try:
            if check_onboarding_completion(db, touchpoint.candidate_id, offer_id, touchpoint.tenant_id):
                result["completions_detected"] += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[OnboardingAgent] Completion check failed for offer_id={offer_id}: {exc}")

    return result
