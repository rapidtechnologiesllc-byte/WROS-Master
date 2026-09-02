"""
import logging
S-020/HRMS-0420 -- Engagement SLA Monitoring.

Scoping decision, 2026-07-24: this codebase already has two systems
that overlap with the spec's three SLA rules:

  - SLA-1 (first contact, 60s) is already measured per-message by
    S-012/S-013's SLA_MET/SLA_BREACH ConversationEvents.
  - SLA-2 (response time) and, informally, SLA-3 are already handled
    *actively* by app.services.conversation_inactivity_service, which
    doesn't just detect staleness -- it self-heals (Thunder reclaims
    ownership + sends a check-in, or nudges) on a 30-hour clock, a
    better fit for the standing Thunder-autonomy direction than a
    passive breach record.

What's genuinely missing -- and what this story actually builds -- is
the VISIBILITY layer neither of those provides: a queryable,
resolvable breach ledger a recruiter can see on a dashboard, with an
in-app notification. So this round implements SLA-3 (NO_CONTACT) in
full, real, and tested; FIRST_CONTACT/RESPONSE_TIME stay defined in
CandidateSLABreach.sla_type for future extensibility but are not
populated by this job -- their detection already exists elsewhere,
described above.

No `conversation_messages`/`system_configuration` tables -- reads
CandidateConversation.status/updated_at directly (BR-01's QUALIFYING/
QUALIFIED map onto this codebase's real "open"/"awaiting_candidate"
states, same mapping S-018 established) and the threshold is a module
constant, overridable via SLA_NO_CONTACT_THRESHOLD_HOURS env var --
"configurable without a code deploy" without inventing a settings
table this round didn't otherwise need.

BR-02 (auto-resolve on new message) is implemented by re-evaluation on
every job tick rather than hooking into every outbound-send code path
(WhatsApp/email/portal/web_chat all have distinct send functions) --
a breach whose underlying condition (updated_at within the window
again) no longer holds is resolved the next time the job runs. At a
30-minute cadence this is a deliberate, honest trade-off: correct
within one tick, not real-time, and far lower regression risk than
wiring into every send path this late before launch.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.sla_breach import CandidateSLABreach
from app.models.user import Users

NO_CONTACT_THRESHOLD_HOURS = int(os.getenv("SLA_NO_CONTACT_THRESHOLD_HOURS", "24"))
MONITORED_STATUSES = ("open", "awaiting_candidate")  # real equivalent of QUALIFYING/QUALIFIED, per S-018


def _candidate_name(candidate: Candidate) -> str:
    return " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])).strip() or candidate.candidateEmail


def _assigned_recruiter(db: Session, candidate_id: str) -> Optional[Users]:
    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    if assignment and assignment.assigned_by:
        return db.query(Users).filter(Users.UserID == assignment.assigned_by).first()
    return None


def _no_contact_threshold_hours(db: Session, tenant_id: str) -> int:
    """S-077/HRMS-0477: real per-tenant TenantAIConfig.sla_no_contact_hours,
    falling back to the module-constant default (still env-overridable,
    unchanged pre-S-077 behavior) on any lookup failure."""
    try:
        from app.services.tenant_ai_config_service import get_sla_no_contact_hours
        return get_sla_no_contact_hours(db, tenant_id)
    except Exception:
        return NO_CONTACT_THRESHOLD_HOURS


def _notify_recruiter_of_breach(db: Session, tenant_id: str, candidate: Candidate, threshold_hours: int) -> None:
    from app.services.notification_service import send_notification

    recipient = _assigned_recruiter(db, candidate.candidateID) or db.query(Users).filter(Users.UserID == tenant_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP",
            message=(
                f"Thunder has not heard back from {_candidate_name(candidate)} in "
                f"{threshold_hours} hours. Review their conversation."
            ),
        )
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[SLAMonitoring] Failed to notify recruiter of breach for candidate {candidate.candidateID}: {exc}")


def detect_and_resolve_no_contact_breaches(db: Session, tenant_id: Optional[str] = None) -> Dict[str, int]:
    """
    SLA_MONITORING_JOB body. Creates NO_CONTACT breaches for
    conversations that just crossed the threshold, and resolves any
    existing NO_CONTACT breach whose conversation is no longer stale
    (BR-02). Safe to call repeatedly (idempotent).
    """
    now = datetime.utcnow()

    query = db.query(CandidateConversation).filter(CandidateConversation.status.in_(MONITORED_STATUSES))
    if tenant_id:
        query = query.filter(CandidateConversation.tenant_id == tenant_id)
    conversations = query.all()

    created = 0
    resolved = 0
    for conversation in conversations:
        threshold_hours = _no_contact_threshold_hours(db, conversation.tenant_id)
        threshold = now - timedelta(hours=threshold_hours)
        is_stale = conversation.updated_at is not None and conversation.updated_at < threshold
        existing_breach = (
            db.query(CandidateSLABreach)
            .filter(
                CandidateSLABreach.conversation_id == conversation.id,
                CandidateSLABreach.sla_type == "NO_CONTACT",
                CandidateSLABreach.is_resolved == False,
            )
            .first()
        )

        if is_stale and not existing_breach:
            candidate = db.query(Candidate).filter(Candidate.candidateID == conversation.candidate_id).first()
            if not candidate:
                continue
            breach = CandidateSLABreach(
                tenant_id=conversation.tenant_id, candidate_id=conversation.candidate_id,
                conversation_id=conversation.id, sla_type="NO_CONTACT", breached_at=now, is_resolved=False,
            )
            db.add(breach)
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="sla_breach_detected",
                event_data={"sla_type": "NO_CONTACT", "breached_at": now.isoformat()}, triggered_by="system",
            ))
            db.flush()
            created += 1
            _notify_recruiter_of_breach(db, conversation.tenant_id, candidate, threshold_hours)

            # S-062/HRMS-0462: real intervention-queue wiring.
            from app.services.intervention_queue_service import PRIORITY_HIGH, add_to_queue
            elapsed_hours = round((now - conversation.updated_at).total_seconds() / 3600) if conversation.updated_at else NO_CONTACT_THRESHOLD_HOURS
            add_to_queue(db, conversation.candidate_id, conversation.tenant_id, "SLA_BREACH", f"SLA Breach: {elapsed_hours}h no contact", PRIORITY_HIGH, commit=False)

        elif not is_stale and existing_breach:
            existing_breach.is_resolved = True
            existing_breach.resolved_at = now
            db.add(existing_breach)
            resolved += 1

            from app.services.intervention_queue_service import resolve_queue_items
            resolve_queue_items(db, conversation.candidate_id, conversation.tenant_id, ["SLA_BREACH"], note="Contact resumed", commit=False)

    db.commit()
    return {"checked": len(conversations), "created": created, "resolved": resolved}


def get_active_breaches(db: Session, tenant_id: str) -> List[Dict]:
    """GET /sla/breaches?is_resolved=false -- oldest breach first (most urgent)."""
    now = datetime.utcnow()
    breaches = (
        db.query(CandidateSLABreach)
        .filter(CandidateSLABreach.tenant_id == tenant_id, CandidateSLABreach.is_resolved == False)
        .order_by(CandidateSLABreach.breached_at.asc())
        .all()
    )
    candidate_ids = {b.candidate_id for b in breaches}
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()} if candidate_ids else {}

    result = []
    for b in breaches:
        candidate = candidates_by_id.get(b.candidate_id)
        result.append({
            "candidate_id": b.candidate_id,
            "candidate_name": _candidate_name(candidate) if candidate else b.candidate_id,
            "conversation_id": b.conversation_id,
            "sla_type": b.sla_type,
            "breached_at": b.breached_at,
            "hours_since_breach": round((now - b.breached_at).total_seconds() / 3600.0, 1),
        })
    return result


def get_active_no_contact_breach_for_conversation(db: Session, conversation_id: int) -> Optional[CandidateSLABreach]:
    """Used by the Status Card warning line (⚠ No contact in N hours)."""
    return (
        db.query(CandidateSLABreach)
        .filter(CandidateSLABreach.conversation_id == conversation_id, CandidateSLABreach.sla_type == "NO_CONTACT", CandidateSLABreach.is_resolved == False)
        .order_by(CandidateSLABreach.breached_at.desc())
        .first()
    )
