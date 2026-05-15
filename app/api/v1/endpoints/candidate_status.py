"""
Candidate Status Management API

Endpoints for updating and viewing a candidate's:
  - Account status  : 'Active' | 'Inactive'
  - Pipeline status : 'Applied' | 'Screening' | 'Interview' | 'Pre-Boarding' | 'Onboarded' | 'Rejected'

Routes:
  PUT  /status/{candidate_id}   — update status / pipeline status
  GET  /status/{candidate_id}   — get current status for a candidate
  GET  /status/all              — get status summary for all candidates
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.candidate import Candidate, CandidateStatus
from app.schemas.candidate import CandidateStatusUpdateRequest, CandidateStatusResponse, AllCandidateStatusResponse, StatusActionResponse


router = APIRouter(prefix="/status", tags=["candidate-status"])


# ---------------------------------------------------------------------------
# Valid choices (kept as constants so the Swagger docs show the options)
# ---------------------------------------------------------------------------

VALID_STATUSES = {"Active", "Inactive"}
VALID_PIPELINE_STATUSES = {
    "Applied",
    "Screening",
    "Interview",
    "Pre-Onboarding",
    "Onboarded",
    "Hired",
    "Rejected",
}



# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_status_response(candidate: Candidate, cs: Optional[CandidateStatus]) -> CandidateStatusResponse:
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

    return CandidateStatusResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        status=cs.status if cs else None,
        pipeline_status=cs.piplineStatus if cs else None,
        updated_at=cs.updatedAt if cs else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.put(
    "/{candidate_id}",
    response_model=StatusActionResponse,
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Update candidate account status and/or pipeline status",
)
def update_candidate_status(
    candidate_id: str,
    request: CandidateStatusUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Update the `status` (Active / Inactive) and/or `pipeline_status`
    (Applied → Screening → Interview → Pre-Boarding → Onboarded / Rejected)
    for a candidate.

    At least one of `status` or `pipeline_status` must be provided.
    Both fields are optional in a single call — send only what you want to change.
    """
    # Validate at least one field provided
    if request.status is None and request.pipeline_status is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'status' or 'pipeline_status' must be provided.",
        )

    # Validate allowed values
    if request.status is not None and request.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    if request.pipeline_status is not None and request.pipeline_status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_status '{request.pipeline_status}'. "
                   f"Allowed: {sorted(VALID_PIPELINE_STATUSES)}",
        )

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # Get or create the CandidateStatus row
    cs = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if not cs:
        # Auto-create a status row if it doesn't exist (e.g. legacy candidates)
        cs = CandidateStatus(
            candidateID=candidate_id,
            status="Active",
            piplineStatus="Applied",
        )
        db.add(cs)
        db.flush()

    # Apply updates
    changed_fields = []
    if request.status is not None:
        cs.status = request.status
        changed_fields.append(f"status → {request.status}")

    if request.pipeline_status is not None:
        cs.piplineStatus = request.pipeline_status
        changed_fields.append(f"pipeline_status → {request.pipeline_status}")

    db.commit()
    db.refresh(cs)

    # ── Pool ownership transition: Rejected → Org Pool ────────────────────────
    if request.pipeline_status == "Rejected":
        from app.services.candidate_pool_service import set_org_pool
        set_org_pool(
            candidate_id=candidate_id,
            reason="BU rejected candidate at interview stage \u2014 returned to Org Pool",
            db=db,
            performed_by_id=getattr(user, "UserID", None),
            performed_by_name=getattr(user, "UserName", None),
        )
        db.commit()

    return StatusActionResponse(
        status="success",
        message=f"Candidate '{candidate_id}' updated: {', '.join(changed_fields)}.",
        data=_build_status_response(candidate, cs),
    )


@router.get(
    "/all",
    response_model=AllCandidateStatusResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get status summary for all candidates",
)
def get_all_candidate_statuses(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    status: Optional[str] = None,
    pipeline_status: Optional[str] = None,
):
    """
    Returns account status and pipeline status for every candidate.
    Useful for pipeline dashboards and bulk status views.

    **Optional filters (query params):**
    - `status` — filter by account status (`Active` | `Inactive`)
    - `pipeline_status` — filter by pipeline stage
      (`Applied` | `Screening` | `Interview` | `Pre-Onboarding` | `Onboarded` | `Hired` | `Rejected`)

    Both filters are independent and can be combined.
    """
    # Validate filter values when provided
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    if pipeline_status is not None and pipeline_status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_status '{pipeline_status}'. Allowed: {sorted(VALID_PIPELINE_STATUSES)}",
        )

    # Build query — join CandidateStatus only when a filter is active
    query = db.query(Candidate)

    if status is not None or pipeline_status is not None:
        query = query.join(
            CandidateStatus,
            CandidateStatus.candidateID == Candidate.candidateID,
        )
        if status is not None:
            query = query.filter(CandidateStatus.status == status)
        if pipeline_status is not None:
            query = query.filter(CandidateStatus.piplineStatus == pipeline_status)

    candidates = query.all()

    results = []
    for candidate in candidates:
        cs = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID
        ).first()
        results.append(_build_status_response(candidate, cs))

    return AllCandidateStatusResponse(total=len(results), candidates=results)


@router.get(
    "/{candidate_id}",
    response_model=CandidateStatusResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get status for a specific candidate",
)
def get_candidate_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Returns the current account status and pipeline status for a single candidate.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    cs = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    return _build_status_response(candidate, cs)
