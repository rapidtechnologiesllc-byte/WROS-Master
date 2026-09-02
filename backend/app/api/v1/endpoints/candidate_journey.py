"""
S-059/HRMS-0459 -- Candidate Journey Dashboard
==================================================================
Prefix: /candidates
import logging
Tag:    candidate-journey

GET /candidates/{candidate_id}/journey
    Auth: gated behind the existing candidate.view permission -- this
    is standard candidate-profile visibility, the same gate every
    other candidate-detail read in this codebase already uses; no new
    permission needed (contrast with S-053's offer.readiness_check,
    which existed because of a real, specific RBAC gap this story
    doesn't have).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.logging import logger
from app.schemas.candidate_journey import CandidateJourneyResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.candidate_journey_service import CandidateNotFound, get_candidate_journey

router = APIRouter(tags=["candidate-journey"])


@router.get(
    "/candidates/{candidate_id}/journey",
    response_model=CandidateJourneyResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a candidate's 7-stage pipeline journey (S-059/HRMS-0459)",
    description=(
        "Derives Engaged/Qualifying/Screened/Interview/Offer/Preboarding/Joined "
        "stage status from real, already-built artifacts (conversation, scores, "
        "interviews, offer, joining readiness, employee conversion) -- this "
        "codebase has no literal state-history table or 10-value pipeline enum."
    ),
)
def get_journey(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        return get_candidate_journey(db, candidate_id, tenant_id)
    except CandidateNotFound:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found.")
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        # 2026-08-05 -- real prod report: candidates were hitting "Unable
        # to load journey" with zero diagnosable detail, because any
        # unexpected exception here (a data-shape edge case in one of
        # the ~7 stages' metric computations) surfaced only as a bare
        # 500 with no server-side trace connecting it back to this
        # candidate. Logged with the full traceback now so the next
        # occurrence is actually debuggable instead of a repeat of this
        # same blind investigation.
        logger.exception(f"[CandidateJourney] Unexpected failure building journey for candidate {candidate_id!r}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not build journey for candidate {candidate_id!r}: {exc}")
