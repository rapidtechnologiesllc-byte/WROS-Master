"""
Candidate Pool Ownership API
============================
Routes:
  GET  /candidate-pool/  — candidates (in the caller's business-unit scope) with pool status
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bu_scope import apply_bu_scope_to_candidate_query
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_BU, POOL_ORG
from app.schemas.candidate_ownership import (
    CandidateOwnershipListItem,
    CandidateOwnershipListResponse,
    CandidateOwnershipResponse,
)
from app.services.candidate_pool_service import get_ownership

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
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="List all candidates with their pool ownership status",
)
def list_candidate_pool(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
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

    Business-unit scope (CEO 2026-10-12): the list is first narrowed to what the caller may
    see (org-level: all; everyone else: the Org Pool plus their own BUs' candidates), so
    `bu_id` can only narrow further -- picking another BU yields nothing. Filters run in
    SQL before paging, so a page is never emptied by filtering after the LIMIT.
    """
    if pool_status and pool_status not in VALID_POOL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pool_status '{pool_status}'. Allowed: {sorted(VALID_POOL_STATUSES)}",
        )

    # HRMS-0109 -- scope to the caller's tenant, then to their business units.
    candidate_query = apply_bu_scope_to_candidate_query(
        db, db.query(Candidate).filter(Candidate.tenant_id == user.tenant_id), user,
    )
    bu_owned = select(CandidateOwnership.candidateID).where(
        CandidateOwnership.pool_status == POOL_BU).correlate(None)
    if pool_status == POOL_BU:
        candidate_query = candidate_query.filter(Candidate.candidateID.in_(bu_owned))
    elif pool_status == POOL_ORG:
        candidate_query = candidate_query.filter(~Candidate.candidateID.in_(bu_owned))
    if bu_id is not None:
        candidate_query = candidate_query.filter(Candidate.candidateID.in_(
            select(CandidateOwnership.candidateID).where(CandidateOwnership.owned_by_bu_id == bu_id).correlate(None)))
    all_candidates = candidate_query.order_by(Candidate.candidateID).offset(skip).limit(limit).all()

    results = []
    for c in all_candidates:
        row = get_ownership(c.candidateID, db)
        effective_status = row.pool_status if row else POOL_ORG

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


# ---------------------------------------------------------------------------
# POST  /candidate-pool/{candidate_id}/override
# ---------------------------------------------------------------------------

