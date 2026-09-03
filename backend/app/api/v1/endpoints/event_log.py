"""
S-078/HRMS-0478 -- Event Emission Layer -- API Endpoints
===========================================================
Prefix: /admin/events
import logging
Tag:    event-log

Routes:
  GET /admin/events    Filterable event_log read, admin only.

Auth: tenant.ai_config permission (Super User by default) -- the same
"admin-only, not candidate-scoped" gate this codebase already uses for
/admin/tenant/ai-config, /admin/tenant/thunder-enabled, and /admin/ai-config.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.event_log import EventLogResponse
from app.services.event_emitter_service import get_events

router = APIRouter(prefix="/admin/events", tags=["event-log"])

@router.get(
    "",
    response_model=EventLogResponse,
    summary="Filterable event log — Super User only",
    dependencies=[Depends(require_resource_permission("ai-config", "view"))],
)
def list_events(
    event_type: Optional[str] = Query(None),
    candidate_id: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO datetime -- only events emitted at or after this time"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid since datetime: {since!r}")

    events = get_events(
        db, current_user.UserID, event_type=event_type, candidate_id=candidate_id, since=since_dt, limit=limit,
    )
    return EventLogResponse(total=len(events), events=events)
