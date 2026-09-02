"""
import logging
S-062/HRMS-0462 -- Recruiter Intervention Queue.

This is the real downstream consumer several earlier EPIC-04 stories
(S-046, S-058, S-060, S-061) explicitly named as "not built yet" and
deliberately left their own row/flag as the durable stand-in signal
for. It now exists -- this module wires the 7 real trigger points
Step 2's own integrations table names, each a small, safe, additive
call (never allowed to break the primary flow it's attached to):
  HRMS-0435 escalation           -> conversation_state_service.escalate()/resolve_escalation()
  HRMS-0460 drop risk >= 70      -> drop_risk_service.calculate_drop_risk()
  HRMS-0420 SLA breach           -> sla_monitoring_service.detect_and_resolve_no_contact_breaches()
  HRMS-0446 abandonment >= 70    -> abandonment_scoring_service.calculate_abandonment_score()
  HRMS-0452 no-show              -> interview_no_show_service (no_show_confirmed_at)
  HRMS-0456 offer counter        -> offer_decision_service._handle_counter()
  HRMS-0457 document overdue     -> document_collection_service.run_document_reminder_job()

Real, documented overlap: offer_decision_service._handle_counter()
already calls the generic escalate() as part of its own, already-
shipped behavior -- so a countered offer produces BOTH a generic
ESCALATION item and this story's own specific OFFER_COUNTER item. Not
silently resolved by dropping one; both integrations table entries are
built as spec asks, same posture already established for this
codebase's several other overlapping "candidate went silent"
mechanisms.

BR-02 dedup is enforced at the DB level by the model's own partial
unique index (`WHERE status='OPEN'`) -- add_to_queue() still does an
application-level check first so it can UPDATE reason_detail/priority
on the existing row rather than relying on catching an IntegrityError.

BR-03 auto-resolve is wired at each real "the underlying issue
cleared" point (drop risk recompute, abandonment recompute, escalation
resolution, SLA breach resolution) -- not a separate polling job,
since each of those already runs on its own real cadence/trigger.

Step 4's "resolved items auto-archive after 7 days" needs no separate
archival job or table -- same "no physical archive, just a default
query window" posture S-061's BR-02 already established for the
identical shape of requirement: get_queue() simply excludes RESOLVED
rows older than 7 days by default; nothing is ever deleted.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.recruiter_intervention_queue import PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, RecruiterInterventionQueue
from app.services.whatsapp_routing_service import take_over_conversation

RESOLVED_RETENTION_DAYS = 7  # Step 4


def add_to_queue(db: Session, candidate_id: str, tenant_id: str, queue_reason: str, reason_detail: str, priority: int, *, commit: bool = True) -> Dict:
    """Step 2. Never raises. BR-02: refreshes an existing OPEN item for
    the same (candidate, reason) instead of creating a duplicate.
    commit=False for call sites (e.g. conversation_state_service.escalate(),
    which only flushes) that need this write to land atomically with
    their own caller-owned commit, matching this codebase's existing
    flush-vs-commit convention rather than forcing a premature commit
    mid another function's transaction."""
    try:
        existing = (
            db.query(RecruiterInterventionQueue)
            .filter(
                RecruiterInterventionQueue.tenant_id == tenant_id, RecruiterInterventionQueue.candidate_id == candidate_id,
                RecruiterInterventionQueue.queue_reason == queue_reason, RecruiterInterventionQueue.status == "OPEN",
            )
            .first()
        )
        if existing:
            existing.reason_detail = reason_detail
            existing.priority = priority
            db.add(existing)
            (db.commit() if commit else db.flush())
            return {"outcome": "updated", "id": existing.id}

        item = RecruiterInterventionQueue(tenant_id=tenant_id, candidate_id=candidate_id, queue_reason=queue_reason, reason_detail=reason_detail, priority=priority, status="OPEN")
        db.add(item)
        (db.commit() if commit else db.flush())
        return {"outcome": "created", "id": item.id}
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[InterventionQueue] Failed adding candidate {candidate_id!r} reason {queue_reason!r}: {exc}")
        # commit=True: this call owns its own transaction, safe to roll back
        # to a clean state. commit=False: it's riding inside a caller's own
        # not-yet-committed transaction (e.g. escalate()'s flush-only
        # convention, or a batch job's per-item flush) -- a rollback here
        # would silently discard that caller's already-flushed, unrelated
        # work too. Leave the transaction state to the caller in that case.
        if commit:
            db.rollback()
        return {"outcome": "failed"}


def resolve_queue_items(db: Session, candidate_id: str, tenant_id: str, reasons: List[str], *, note: str = "Auto-resolved: underlying issue cleared", commit: bool = True) -> int:
    """BR-03. Never raises. Resolves OPEN/IN_PROGRESS items -- resolved_by
    stays None (system, not a recruiter)."""
    try:
        items = (
            db.query(RecruiterInterventionQueue)
            .filter(
                RecruiterInterventionQueue.tenant_id == tenant_id, RecruiterInterventionQueue.candidate_id == candidate_id,
                RecruiterInterventionQueue.queue_reason.in_(reasons), RecruiterInterventionQueue.status != "RESOLVED",
            )
            .all()
        )
        now = datetime.utcnow()
        for item in items:
            item.status = "RESOLVED"
            item.resolved_at = now
            item.resolution_note = note
            db.add(item)
        if items:
            (db.commit() if commit else db.flush())
        return len(items)
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[InterventionQueue] Failed auto-resolving candidate {candidate_id!r} reasons {reasons}: {exc}")
        if commit:  # see add_to_queue()'s identical reasoning
            db.rollback()
        return 0


def _candidate_name(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return "Unknown candidate"
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    return " ".join(p for p in parts if p).strip() or candidate.candidateEmail


def get_queue(db: Session, tenant_id: str, *, status: Optional[str] = None, retention_days: int = RESOLVED_RETENTION_DAYS) -> List[Dict]:
    """Step 3. BR-01: CRITICAL (priority=1) always sorts first, then
    HIGH, then MEDIUM; oldest-first within the same priority."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    query = db.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.tenant_id == tenant_id)
    if status:
        query = query.filter(RecruiterInterventionQueue.status == status)
    else:
        # Default view: everything OPEN/IN_PROGRESS, plus RESOLVED within the retention window.
        from sqlalchemy import or_
        query = query.filter(or_(RecruiterInterventionQueue.status != "RESOLVED", RecruiterInterventionQueue.resolved_at >= cutoff))

    items = query.order_by(RecruiterInterventionQueue.priority.asc(), RecruiterInterventionQueue.added_at.asc()).all()

    candidate_ids = {i.candidate_id for i in items}
    candidates_by_id = {c.candidateID: c for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()} if candidate_ids else {}

    return [
        {
            "id": i.id, "candidate_id": i.candidate_id, "candidate_name": _candidate_name(candidates_by_id.get(i.candidate_id)),
            "queue_reason": i.queue_reason, "reason_detail": i.reason_detail, "priority": i.priority, "status": i.status,
            "assigned_to_user_id": i.assigned_to_user_id, "added_at": i.added_at, "resolved_at": i.resolved_at, "resolution_note": i.resolution_note,
        }
        for i in items
    ]


def get_queue_summary(db: Session, tenant_id: str) -> Dict:
    """Step 3's dashboard widget: OPEN item counts by priority."""
    open_items = db.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.tenant_id == tenant_id, RecruiterInterventionQueue.status == "OPEN").all()
    return {
        "critical": sum(1 for i in open_items if i.priority == PRIORITY_CRITICAL),
        "high": sum(1 for i in open_items if i.priority == PRIORITY_HIGH),
        "medium": sum(1 for i in open_items if i.priority == PRIORITY_MEDIUM),
        "total": len(open_items),
    }

logger = logging.getLogger(__name__)

class QueueItemNotFound(Exception):
    pass


def take_over_queue_item(db: Session, queue_item_id: int, tenant_id: str, recruiter_user_id: str) -> Dict:
    """Step 3's 'Take Over' button. Reuses HRMS-0410's real
    take_over_conversation() -- never duplicates ownership-transfer logic."""
    item = db.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == queue_item_id, RecruiterInterventionQueue.tenant_id == tenant_id).first()
    if item is None:
        raise QueueItemNotFound(f"Queue item {queue_item_id} not found.")

    conversation = db.query(CandidateConversation).filter(CandidateConversation.candidate_id == item.candidate_id).order_by(CandidateConversation.id.desc()).first()
    if conversation is not None:
        take_over_conversation(db, conversation, recruiter_user_id)

    item.status = "IN_PROGRESS"
    item.assigned_to_user_id = recruiter_user_id
    db.add(item)
    db.commit()
    return {"id": item.id, "status": item.status, "assigned_to_user_id": item.assigned_to_user_id}


def mark_resolved(db: Session, queue_item_id: int, tenant_id: str, recruiter_user_id: str, resolution_note: Optional[str] = None) -> Dict:
    """Step 4's 'Mark Resolved' button."""
    item = db.query(RecruiterInterventionQueue).filter(RecruiterInterventionQueue.id == queue_item_id, RecruiterInterventionQueue.tenant_id == tenant_id).first()
    if item is None:
        raise QueueItemNotFound(f"Queue item {queue_item_id} not found.")

    item.status = "RESOLVED"
    item.resolved_at = datetime.utcnow()
    item.resolved_by = recruiter_user_id
    item.resolution_note = resolution_note
    db.add(item)
    db.commit()
    return {"id": item.id, "status": item.status, "resolved_at": item.resolved_at}
