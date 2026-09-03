"""
import logging
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.

write_timeline_entry() is BR-0118-01's one sanctioned write path -- any
story needing a history feed calls this instead of building its own
history table.
"""
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.activity_timeline import ActivityTimeline

DEFAULT_PAGE_SIZE = 25

def write_timeline_entry(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    tenant_id: Optional[int] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "USER",
    description: Optional[str] = None,
) -> ActivityTimeline:
    """Caller commits, same 'function mutates state, caller owns the
    transaction' convention as app.core.audit.write_audit_log()."""
    entry = ActivityTimeline(
        tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
        actor_id=actor_id, actor_type=actor_type, action=action, description=description,
    )
    db.add(entry)
    return entry

def get_timeline_for_entity(
    db: Session, entity_type: str, entity_id: str, *,
    tenant_id: Optional[int] = None, page: int = 1, per_page: int = DEFAULT_PAGE_SIZE,
) -> Dict:
    """AC-1: works for any entity_type without a schema change. Paginated,
    newest first, per the spec's own UI Fields row."""
    query = db.query(ActivityTimeline).filter(
        ActivityTimeline.entity_type == entity_type, ActivityTimeline.entity_id == entity_id,
    )
    if tenant_id is not None:
        query = query.filter(ActivityTimeline.tenant_id == tenant_id)
    # id as a tiebreaker -- created_at alone can tie under load (or on
    # SQLite, whose CURRENT_TIMESTAMP has only 1-second resolution),
    # and the autoincrement id is strictly monotonic with insert order.
    query = query.order_by(ActivityTimeline.created_at.desc(), ActivityTimeline.id.desc())

    total = query.count()
    entries = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "entries": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "actor_type": e.actor_type,
                "action": e.action,
                "description": e.description,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }
