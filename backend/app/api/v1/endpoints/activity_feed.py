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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.schemas.activity_feed import ActivityFeedResponse, MarkAllReadResponse
from app.services.activity_feed_service import get_activity_feed, mark_all_read, mark_read

router = APIRouter(prefix="/activity-feed", tags=["activity-feed"])


def _visible_candidate_ids(db: Session, user):
    """The candidates whose activity the caller may see -- the Org Pool plus their business
    units' candidates (app.core.bu_scope, the one candidate rule); None for org-level users."""
    from app.core.bu_scope import apply_bu_scope_to_candidate_query, is_bu_restricted
    from app.models.candidate import Candidate

    if not is_bu_restricted(db, user):
        return None
    scoped = apply_bu_scope_to_candidate_query(db, db.query(Candidate.candidateID), user).subquery()
    return select(scoped.c.candidateID)

@router.get("", response_model=ActivityFeedResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_activity_feed(
    candidate_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    return get_activity_feed(
        db, current_user.tenant_id, candidate_id=candidate_id, severity=severity, page=page, per_page=per_page,
        visible_candidate_ids=_visible_candidate_ids(db, current_user),
    )

@router.patch("/{activity_id}/read", dependencies=[Depends(require_resource_permission("candidates", "view"))])
def mark_activity_read(activity_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_internal_user)):
    ok = mark_read(db, current_user.UserID, activity_id)
    return {"marked": ok}

@router.patch("/read-all", response_model=MarkAllReadResponse, dependencies=[Depends(require_resource_permission("candidates", "view"))])
def mark_activity_feed_read_all(
    candidate_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    count = mark_all_read(db, current_user.tenant_id, current_user.UserID, candidate_id=candidate_id)
    return MarkAllReadResponse(marked_count=count)

