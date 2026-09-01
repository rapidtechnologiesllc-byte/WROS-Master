"""
Candidate History API
=====================
Provides a chronological audit trail / timeline for every candidate.

Routes:
  POST  /history/{candidate_id}         — log a new timeline event
  GET   /history/{candidate_id}         — get full history for a candidate
  GET   /history/{candidate_id}/latest  — get the most recent N events
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.schemas.candidate_history import (
    VALID_EVENT_TYPES,
    CandidateHistoryCreateRequest,
    CandidateHistoryCreateResponse,
    CandidateHistoryListResponse,
    CandidateHistoryResponse,
)


router = APIRouter(prefix="/history", tags=["candidate-history"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(h: CandidateHistory) -> CandidateHistoryResponse:
    return CandidateHistoryResponse(
        id=h.id,
        candidate_id=h.candidateID,
        event_type=h.event_type,
        note=h.note,
        performed_by_id=h.performed_by_id,
        performed_by_name=h.performed_by_name,
        job_id=h.job_id,
        interview_id=h.interview_id,
        offer_letter_id=h.offer_letter_id,
        event_at=h.event_at,
        created_at=h.createdAt,
    )


def _get_candidate_or_404(candidate_id: str, db: Session) -> Candidate:
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return candidate


# ---------------------------------------------------------------------------
# POST  /history/{candidate_id}  — create a new history event
# ---------------------------------------------------------------------------

@router.post(
    "/{candidate_id}",
    response_model=CandidateHistoryCreateResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("history", "create"))],
    summary="Log a new timeline event for a candidate",
)
def create_candidate_history(
    candidate_id: str,
    request: CandidateHistoryCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Record a new event in the candidate's history / timeline.

    **event_type** must be one of:
    - `Applied` — candidate applied for a job
    - `Candidate Added` — candidate was added to the platform
    - `Candidate Edited` — candidate profile details were edited
    - `Screening` — HR screened the candidate
    - `Job Assigned` — candidate was assigned to a job
    - `Interview Scheduled` — interview has been scheduled
    - `Feedback Submitted` — interviewer feedback was submitted
    - `Interview Completed` — interview was conducted
    - `Interview Rescheduled` — interview was rescheduled
    - `Interview Cancelled` — interview was cancelled
    - `Candidate No Show` — candidate did not show up for the interview
    - `Preonboarding Document Rejected` — a pre-onboarding document was rejected
    - `Candidate Archived` — candidate was archived
    - `Candidate Restored` — candidate was restored from archive
    - `Offer Updated` — offer letter details were updated
    - `Preonboarding Approval` — pre-onboarding approval event
    - `Preonboarding` — general pre-onboarding action
    - `Preonboarding document verifiy` — a pre-onboarding document was verified
    - `Offer Released` — offer letter was generated & sent
    - `Offer Accepted` — candidate accepted the offer
    - `Offer Rejected` — candidate rejected the offer
    - `Pre-Onboarding` — pre-onboarding tasks started
    - `Onboarded` — candidate has joined
    - `Rejected` — candidate was rejected at any stage
    - `Custom` — any other freeform event (describe it in `note`)

    The `performed_by_id` / `performed_by_name` default to the calling user's
    details if not explicitly supplied in the request body.
    """
    # Validate candidate exists
    _get_candidate_or_404(candidate_id, db)

    # Validate event_type
    if request.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid event_type '{request.event_type}'. "
                f"Allowed: {sorted(VALID_EVENT_TYPES)}"
            ),
        )

    # Resolve performer — fall back to the calling user if not supplied
    performed_by_id = request.performed_by_id or getattr(user, "userID", None)
    performed_by_name = request.performed_by_name or (
        f"{getattr(user, 'userFirstName', '') or ''} "
        f"{getattr(user, 'userLastName', '') or ''}".strip()
        or getattr(user, "userEmail", None)
    )

    event_at = request.event_at or datetime.utcnow()

    history_row = CandidateHistory(
        candidateID=candidate_id,
        event_type=request.event_type,
        note=request.note,
        performed_by_id=performed_by_id,
        performed_by_name=performed_by_name,
        job_id=request.job_id,
        interview_id=request.interview_id,
        offer_letter_id=request.offer_letter_id,
        event_at=event_at,
    )

    db.add(history_row)
    db.commit()
    db.refresh(history_row)

    logger.info(
        f"candidate_history — event '{request.event_type}' logged "
        f"for candidate '{candidate_id}' by '{performed_by_id}'"
    )

    return CandidateHistoryCreateResponse(
        status="success",
        message=f"Event '{request.event_type}' logged for candidate '{candidate_id}'.",
        event=_to_response(history_row),
    )


# ---------------------------------------------------------------------------
# GET  /history/{candidate_id}  — full timeline (paginated)
# ---------------------------------------------------------------------------

@router.get(
    "/{candidate_id}",
    response_model=CandidateHistoryListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get the full history / timeline for a candidate",
)
def get_candidate_history(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type (e.g. 'Interview Scheduled')",
    ),
    skip: int = Query(default=0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return (1–200)"),
):
    """
    Returns the chronological timeline of events for a single candidate,
    ordered newest-first.

    **Optional query parameters:**
    - `event_type` — filter to a specific event type
    - `skip` / `limit` — standard pagination
    """
    _get_candidate_or_404(candidate_id, db)

    query = db.query(CandidateHistory).filter(
        CandidateHistory.candidateID == candidate_id
    )

    if event_type:
        query = query.filter(CandidateHistory.event_type == event_type)

    total = query.count()
    events = (
        query.order_by(CandidateHistory.event_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return CandidateHistoryListResponse(
        candidate_id=candidate_id,
        total=total,
        events=[_to_response(e) for e in events],
    )


# ---------------------------------------------------------------------------
# GET  /history/{candidate_id}/latest  — last N events (convenience endpoint)
# ---------------------------------------------------------------------------

@router.get(
    "/{candidate_id}/latest",
    response_model=CandidateHistoryListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get the N most recent history events for a candidate",
)
def get_latest_candidate_history(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
    n: int = Query(default=10, ge=1, le=100, description="How many recent events to return (1–100)"),
):
    """
    Convenience endpoint — returns the `n` most recent timeline events for a
    candidate. Useful for dashboards that show a summary card.
    """
    _get_candidate_or_404(candidate_id, db)

    total = (
        db.query(CandidateHistory)
        .filter(CandidateHistory.candidateID == candidate_id)
        .count()
    )
    events = (
        db.query(CandidateHistory)
        .filter(CandidateHistory.candidateID == candidate_id)
        .order_by(CandidateHistory.event_at.desc())
        .limit(n)
        .all()
    )

    return CandidateHistoryListResponse(
        candidate_id=candidate_id,
        total=total,
        events=[_to_response(e) for e in events],
    )
