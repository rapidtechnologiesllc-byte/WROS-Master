"""
S-053/HRMS-0453 -- Offer Readiness Check
==================================================================
Prefix: /candidates
import logging
Tag:    offer-readiness

GET /candidates/{candidate_id}/jobs/{job_id}/offer-readiness
    Auth: gated behind offer.readiness_check -- a new, narrower
    permission than offer.manage/offer.view (see rbac_service.py's own
    note), added specifically so Recruiter gets a real HTTP 403 here
    per this story's own explicit AC/TC, without touching the two
    broader offer permissions other already-shipped routes depend on.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.schemas.offer_readiness import OfferReadinessResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.offer_readiness_service import check_offer_readiness

router = APIRouter(tags=["offer-readiness"])

@router.get(
    "/candidates/{candidate_id}/jobs/{job_id}/offer-readiness",
    response_model=OfferReadinessResponse,
    dependencies=[Depends(require_resource_permission("offer-letters", "view"))],
    summary="Check whether a candidate is ready for an offer (S-053/HRMS-0453)",
    description=(
        "Validates L1+L2 interview PASS (BR-01), no COMPLIANCE_BLOCK flag, no "
        "withdrawn/rejected submission, and the >=5yr experience floor "
        "(BR-02, re-validated). COMPENSATION_MISMATCH is a warning only (BR-03), "
        "never a blocker."
    ),
)
def get_offer_readiness(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    result = check_offer_readiness(db, candidate_id, job_id, tenant_id)
    return OfferReadinessResponse(is_ready=result["is_ready"], blockers=result["blockers"], warnings=result["warnings"], checked_at=datetime.utcnow())
