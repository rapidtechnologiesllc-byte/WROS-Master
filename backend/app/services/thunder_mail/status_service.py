"""Where Thunder stands with one candidate, for the candidate profile: its last email, the
candidate's last reply, what it sends next and when, and the profile details it is still asking for."""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage
from app.services.thunder_mail import cadence_service as cadence

STAGE_LABELS = {
    "ACTIVE": "Reaching out", "NURTURE": "Monthly check-in", "HANDOFF": "Talking with a recruiter",
    "STOPPED": "Stopped",
}


def next_step_label(step: Optional[str]) -> Optional[str]:
    if not step:
        return None
    family = cadence.step_family(step)
    if family == cadence.DETAILS:
        return "Reminder for missing details"
    if family == "NURTURE":
        return "Monthly check-in"
    if family.isdigit():
        return "First email" if family == "1" else f"Follow-up {int(family) - 1}"
    return "Reply to the candidate"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def thunder_status(db: Session, candidate: Candidate) -> Dict[str, Any]:
    from app.services.ai_conversation_service import get_missing_fields

    state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).first()
    last_out = db.query(ThunderEmailMessage).filter(
        ThunderEmailMessage.candidate_id == candidate.candidateID, ThunderEmailMessage.direction == "OUT",
        ThunderEmailMessage.status == "SENT",
    ).order_by(ThunderEmailMessage.sent_at.desc()).first()
    last_in = db.query(ThunderEmailMessage).filter(
        ThunderEmailMessage.candidate_id == candidate.candidateID, ThunderEmailMessage.direction == "IN",
    ).order_by(ThunderEmailMessage.received_at.desc()).first()
    emails_sent = db.query(ThunderEmailMessage.id).filter(
        ThunderEmailMessage.candidate_id == candidate.candidateID, ThunderEmailMessage.direction == "OUT",
        ThunderEmailMessage.status == "SENT",
    ).count()
    stopped = state is None or state.stage == "STOPPED"
    return {
        "thunder_enabled": candidate.thunder_enabled is not False,
        "enrolled": state is not None,
        "stage": state.stage if state else None,
        "stage_label": STAGE_LABELS.get(state.stage, state.stage) if state else "Not contacted yet",
        "stop_reason": state.stop_reason if state else None,
        "emails_sent": emails_sent,
        "last_email_at": _iso(last_out.sent_at) if last_out else None,
        "last_email_subject": last_out.subject if last_out else None,
        "last_reply_at": _iso(last_in.received_at) if last_in else None,
        "last_reply_intent": last_in.intent if last_in else None,
        "next_step_label": None if stopped else next_step_label(state.next_step),
        "next_action_at": None if stopped else _iso(state.next_action_at),
        "missing_fields": [m["label"] for m in get_missing_fields(candidate, db, include_documents=True)],
    }
