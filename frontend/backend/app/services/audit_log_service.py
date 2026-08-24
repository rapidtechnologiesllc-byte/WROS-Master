"""
S-076/HRMS-0476 -- AuditLogger service.

A simple INSERT function -- no business logic, no transformations, no
side effects. Callers must invoke this within the same DB session/
transaction as the action being audited, so if the insert fails, the
exception propagates and the caller's own commit fails too -- an action
that cannot be audited does not silently proceed (BR-02).
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.conversation_audit_log import ConversationAuditLog


def log_audit_event(
    db: Session,
    *,
    tenant_id: str,
    candidate_id: str,
    audit_event_type: str,
    description: str,
    actor_type: str,
    actor_id: str,
    conversation_id: Optional[int] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
) -> ConversationAuditLog:
    entry = ConversationAuditLog(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        conversation_id=conversation_id,
        audit_event_type=audit_event_type,
        audit_event_description=description,
        actor_type=actor_type,
        actor_id=actor_id,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(entry)
    db.flush()  # surfaces any DB error immediately, before the caller commits
    return entry
