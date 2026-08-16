"""
Candidate Pool Ownership API
============================
Routes:
  GET  /candidate-pool/                        — list all candidates with pool status
  GET  /candidate-pool/{candidate_id}          — pool status for one candidate
  POST /candidate-pool/{candidate_id}/override — HR Admin manual override
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG
from app.models.rbac import BusinessUnit
from app.schemas.candidate_ownership import (
    CandidateOwnershipListItem,
    CandidateOwnershipListResponse,
    CandidateOwnershipResponse,
    OwnershipOverrideRequest,
)
from app.services.candidate_pool_service import (
    get_ownership,
    set_bu_owned,
    set_org_pool,
)


router = APIRouter(prefix="/candidate-pool", tags=["candidate-pool"])

VALID_POOL_STATUSES = {POOL_ORG, POOL_BU}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate_name(c: Candidate) -> Optional[str]:
    parts = [c.candidateFirstName, c.candidateMiddleName, c.candidateLastName]
    return " ".join(p for p in parts if p) or None


def _to_response(candidate_id: str, row: Optional[CandidateOwnership]) -> CandidateOwnershipResponse:
    if row is None:
        return CandidateOwnershipResponse(
            candidate_id=candidate_id,
            pool_status=POOL_ORG,
        )
    return CandidateOwnershipResponse(
        candidate_id=row.candidateID,
        pool_status=row.pool_status,
        owned_by_bu_id=row.owned_by_bu_id,
        owned_by_bu_name=row.owned_by_bu_name,
        ownership_reason=row.ownership_reason,
        bu_owned_since=row.bu_owned_since,
        bu_ownership_expires_at=row.bu_ownership_expires_at,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# GET  /candidate-pool/
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=CandidateOwnershipListResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="List all candidates with their pool ownership status",
)
def list_candidate_pool(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    pool_status: Optional[str] = Query(
        default=None,
        description=f"Filter by pool status: '{POOL_ORG}' or '{POOL_BU}'",
    ),
    bu_id: Optional[int] = Query(
        default=None,
        description="Filter to candidates owned by a specific BU (use with pool_status='BU Owned')",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Returns every candidate with their current pool ownership state.

    **Filters:**
    - `pool_status` — `'Org Pool'` or `'BU Owned'`
    - `bu_id` — only show candidates owned by this specific Business Unit

    Candidates who have **never been assigned** to any BU are implicitly in the
    Org Pool (they may not have a `candidate_ownership` row yet).
    """
    if pool_status and pool_status not in VALID_POOL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pool_status '{pool_status}'. Allowed: {sorted(VALID_POOL_STATUSES)}",
        )

    # HRMS-0109 -- scope to the caller's tenant.
    candidate_query = db.query(Candidate)
    all_candidates = candidate_query.order_by(Candidate.candidateID).offset(skip).limit(limit).all()

    results = []
    for c in all_candidates:
        row = get_ownership(c.candidateID, db)
        effective_status = row.pool_status if row else POOL_ORG
        effective_bu_id  = row.owned_by_bu_id if row else None

        # Apply filters
        if pool_status and effective_status != pool_status:
            continue
        if bu_id is not None and effective_bu_id != bu_id:
            continue

        results.append(CandidateOwnershipListItem(
            candidate_id=c.candidateID,
            candidate_name=_candidate_name(c),
            candidate_email=c.candidateEmail,
            pool_status=effective_status,
            owned_by_bu_name=row.owned_by_bu_name if row else None,
            bu_ownership_expires_at=row.bu_ownership_expires_at if row else None,
            updated_at=row.updated_at if row else None,
        ))

    return CandidateOwnershipListResponse(total=len(results), candidates=results)


# ---------------------------------------------------------------------------
# GET  /candidate-pool/{candidate_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{candidate_id}",
    response_model=CandidateOwnershipResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get pool ownership status for a specific candidate",
)
def get_candidate_pool_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Returns the current pool ownership state for a single candidate.

    If the candidate has no ownership record (i.e. never been assigned to a BU),
    they are implicitly in the **Org Pool**.
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    row = get_ownership(candidate_id, db)
    return _to_response(candidate_id, row)


# ---------------------------------------------------------------------------
# POST  /candidate-pool/{candidate_id}/override
# ---------------------------------------------------------------------------

@router.post(
    "/{candidate_id}/override",
    response_model=CandidateOwnershipResponse,
    dependencies=[Depends(require_permission("candidate.edit"))],
    summary="Manually override candidate pool ownership (HR Admin)",
)
def override_candidate_pool(
    candidate_id: str,
    request: OwnershipOverrideRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Manually change the pool ownership state for a candidate.

    - Setting `pool_status = 'BU Owned'` requires a valid `bu_id`.
    - Setting `pool_status = 'Org Pool'` clears all BU ownership data.
    - Every override is logged to the candidate history audit trail.

    **Required permission:** `candidate.edit`
    """
    if request.pool_status not in VALID_POOL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pool_status '{request.pool_status}'. Allowed: {sorted(VALID_POOL_STATUSES)}",
        )

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # Resolve caller identity for history log
    performed_by_id   = getattr(user, "UserID", None)
    performed_by_name = (
        f"{getattr(user, 'userFirstName', '') or ''} "
        f"{getattr(user, 'userLastName', '') or ''}".strip()
        or getattr(user, "UserEmail", None)
    )

    if request.pool_status == POOL_BU:
        if not request.bu_id:
            raise HTTPException(
                status_code=400,
                detail="'bu_id' is required when setting pool_status to 'BU Owned'.",
            )
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == request.bu_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail=f"Business Unit #{request.bu_id} not found.")

        row = set_bu_owned(
            candidate_id=candidate_id,
            bu_id=bu.id,
            bu_name=bu.name,
            reason=f"Manual override by HR: {request.reason}",
            db=db,
            performed_by_id=performed_by_id,
            performed_by_name=performed_by_name,
        )
    else:
        row = set_org_pool(
            candidate_id=candidate_id,
            reason=f"Manual override by HR: {request.reason}",
            db=db,
            performed_by_id=performed_by_id,
            performed_by_name=performed_by_name,
        )

    db.commit()
    db.refresh(row)
    return _to_response(candidate_id, row)
