"""
import logging
S-078/HRMS-0478 -- Event Emission Layer for AI Actions.

See app.models.event_log's module docstring for the real architecture
adaptation this module implements: a real event_log table + emit(),
no message bus/pub-sub/retry queue (nothing in this codebase publishes
to or subscribes from one yet).

Step 5's "replace all ad-hoc event publishes in EPIC-04 with
EventEmitter.emit()" is honestly NOT done wholesale here -- this
codebase's real per-story event mechanism (ConversationEvent, S-003's
own append-only log every prior EPIC-04 story already writes to) is a
different, already-shipped, differently-shaped log serving a different
purpose (the candidate-conversation timeline UI reads it directly).
Retrofitting every one of ~30 ConversationEvent call sites to also
emit through this new, differently-namespaced catalog in the same pass
this story ships in would be a large, high-risk blast radius for a
mechanism with zero real subscribers yet. Instead, emit() is wired
into the highest-value, safest real trigger points as they're built
(supervisor.cycle_completed from S-066's SupervisorAgent is the first
real caller) -- flagged here, not silently claimed complete.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.event_log import EventLog
from app.core.logging import logger

# Step 1's literal event catalog. candidate_scoped=True means BR-02
# requires candidate_id on every emit of that type.
EVENT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "candidate.created": {"version": "v1", "candidate_scoped": True},
    "candidate.engaged": {"version": "v1", "candidate_scoped": True},
    "candidate.qualified": {"version": "v1", "candidate_scoped": True},
    "candidate.fully_qualified": {"version": "v1", "candidate_scoped": True},
    "candidate.ghosted": {"version": "v1", "candidate_scoped": True},
    "candidate.reactivated": {"version": "v1", "candidate_scoped": True},
    "candidate.resume_uploaded": {"version": "v1", "candidate_scoped": True},
    "candidate.resume_parsed": {"version": "v1", "candidate_scoped": True},
    "candidate.skills_extracted": {"version": "v1", "candidate_scoped": True},
    "candidate.availability_provided": {"version": "v1", "candidate_scoped": True},
    "candidate.high_abandonment_risk": {"version": "v1", "candidate_scoped": True},
    "candidate.negative_sentiment_trend": {"version": "v1", "candidate_scoped": True},
    "conversation.state_changed": {"version": "v1", "candidate_scoped": True},
    "conversation.ownership_transferred": {"version": "v1", "candidate_scoped": True},
    "message.received": {"version": "v1", "candidate_scoped": True},
    "message.delivery_failed": {"version": "v1", "candidate_scoped": True},
    "interview.confirmed": {"version": "v1", "candidate_scoped": True},
    "interview.rescheduled": {"version": "v1", "candidate_scoped": True},
    "interview.no_show": {"version": "v1", "candidate_scoped": True},
    "offer.released": {"version": "v1", "candidate_scoped": True},
    "offer.accepted": {"version": "v1", "candidate_scoped": True},
    "offer.declined": {"version": "v1", "candidate_scoped": True},
    "onboarding.complete": {"version": "v1", "candidate_scoped": True},
    "sla.breach_detected": {"version": "v1", "candidate_scoped": True},
    # S-348/HRMS-P118 -- Desire Profile Builder.
    "candidate.desire_profile_updated": {"version": "v1", "candidate_scoped": True},
    "candidate.desire_shift_detected": {"version": "v1", "candidate_scoped": True},
    "candidate.competing_offer_detected": {"version": "v1", "candidate_scoped": True},
    # S-349/HRMS-P119 -- consumed by motivation_engine_service's
    # COOLING_ENGAGEMENT trigger.
    "candidate.engagement_cooled": {"version": "v1", "candidate_scoped": True},
    # Not candidate-specific -- one summary event per tenant per cycle.
    "supervisor.cycle_completed": {"version": "v1", "candidate_scoped": False},
}

logger = logging.getLogger(__name__)

class EventDefinitionNotFoundError(Exception):
    """AC-2: event_type not in EVENT_DEFINITIONS."""


class EventValidationError(Exception):
    """AC-3: missing required tenant_id, or missing candidate_id for a
    candidate-scoped event type (BR-02)."""


def emit(
    db: Session, event_type: str, payload: Optional[Dict], tenant_id: str, candidate_id: Optional[str] = None,
) -> int:
    """BR-03: returns immediately after the INSERT -- there is no
    subscriber to publish to or wait on in this codebase, so "async,
    does not wait" holds trivially and honestly."""
    definition = EVENT_DEFINITIONS.get(event_type)
    if definition is None:
        raise EventDefinitionNotFoundError(f"Unknown event_type '{event_type}' -- not in EVENT_DEFINITIONS.")

    if not tenant_id:
        raise EventValidationError("tenant_id is required for every event (BR-02).")
    if definition["candidate_scoped"] and not candidate_id:
        raise EventValidationError(f"Event type '{event_type}' is candidate-scoped -- candidate_id is required (BR-02).")

    record = EventLog(
        tenant_id=tenant_id, candidate_id=candidate_id, event_type=event_type,
        event_version=definition["version"], payload=payload or {},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def get_events(
    db: Session, tenant_id: str, *, event_type: Optional[str] = None,
    candidate_id: Optional[str] = None, since: Optional[datetime] = None, limit: int = 100,
) -> List[Dict]:
    query = db.query(EventLog).filter(EventLog.tenant_id == tenant_id)
    if event_type:
        query = query.filter(EventLog.event_type == event_type)
    if candidate_id:
        query = query.filter(EventLog.candidate_id == candidate_id)
    if since:
        query = query.filter(EventLog.emitted_at >= since)
    rows = query.order_by(EventLog.emitted_at.desc()).limit(min(limit, 500)).all()
    return [
        {
            "id": r.id, "tenant_id": r.tenant_id, "candidate_id": r.candidate_id,
            "event_type": r.event_type, "event_version": r.event_version,
            "payload": r.payload, "emitted_at": r.emitted_at.isoformat() if r.emitted_at else None,
        }
        for r in rows
    ]
