"""
S-061/HRMS-0461 -- AI Activity Feed, Recruiter Copilot
==================================================================
Prefix: /activity-feed
Tag:    activity-feed

GET /activity-feed?candidate_id={optional}&severity={optional}&page=1&per_page=25
    Global feed (no candidate_id) or per-candidate feed (Messages Tab).
PATCH /activity-feed/{id}/read
    Marks a single activity read (idempotent).
PATCH /activity-feed/read-all?candidate_id={optional}
    BR-01: only clears INFO/WARNING -- ACTION_REQUIRED items are never
    auto-marked read here.

Auth: candidate.view -- same read-only recruiter visibility gate as
S-059/S-060's endpoints; this story has no distinct RBAC requirement
of its own.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.schemas.activity_feed import ActivityFeedResponse, MarkAllReadResponse
from app.services.activity_feed_service import get_activity_feed, mark_all_read, mark_read
from app.services.ai_conversation_service import resolve_default_tenant_id

router = APIRouter(prefix="/activity-feed", tags=["activity-feed"])


@router.get("", response_model=ActivityFeedResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_activity_feed(
    candidate_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    tenant_id = resolve_default_tenant_id(db)
    return get_activity_feed(db, tenant_id, candidate_id=candidate_id, severity=severity, page=page, per_page=per_page)


@router.patch("/{activity_id}/read", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def mark_activity_read(activity_id: int, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    ok = mark_read(db, tenant_id, activity_id)
    return {"marked": ok}


@router.patch("/read-all", response_model=MarkAllReadResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def mark_activity_feed_read_all(candidate_id: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    count = mark_all_read(db, tenant_id, candidate_id=candidate_id)
    return MarkAllReadResponse(marked_count=count)


@router.get("/standup", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_daily_standup(days: int = Query(default=1, ge=1, le=30), db: Session = Depends(get_db)):
    """
    Get daily standup report showing:
    - How many candidates Thunder reached
    - SLA compliance (met vs missed)
    - Success rate percentage
    - List of all candidates contacted with timestamps
    """
    from app.services.daily_standup_service import get_daily_standup
    return get_daily_standup(db, days=days)


@router.get("/flash/standup", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def get_flash_standup_report(days: int = Query(default=1, ge=1, le=30), db: Session = Depends(get_db)):
    """
    Get Flash's daily standup report on Thunder's SLA compliance.
    Shows appreciations, punishments, and success rate.
    """
    from app.services.flash_sla_validation import get_daily_standup_report
    return get_daily_standup_report(db, days=days)
