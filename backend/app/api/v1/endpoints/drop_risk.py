"""
S-060/HRMS-0460 -- Drop Risk Prediction
==================================================================
Prefix: /candidates
Tag:    drop-risk

GET /candidates/{candidate_id}/drop-risk
    Auth: gated behind the existing candidate.view permission -- same
    read-only visibility gate as S-059's journey endpoint; this story
    has no real, specific RBAC gap the way S-053's offer.readiness_check
    did.

Scope note: this story's own Step 4 says "add drop_risk_score/risk_level
to GET /api/candidates/{id}" -- built instead as its own additive
endpoint rather than modifying the shared, already-relied-upon core
candidate serializer, same "extend, don't risk shipped code" judgment
S-056 used for its own pipeline-status helper. Recalculates fresh on
every read (same on-demand posture as S-053's offer-readiness check),
in addition to the periodic 4-hour job.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.schemas.drop_risk import DropRiskResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.drop_risk_service import calculate_drop_risk

router = APIRouter(tags=["drop-risk"])


@router.get(
    "/candidates/{candidate_id}/drop-risk",
    response_model=DropRiskResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a candidate's drop risk score (S-060/HRMS-0460)",
    description=(
        "Stage-gated 0-100 drop risk score (abandonment/sentiment/stage-time for "
        "QUALIFYING, response-rate/reschedules for INTERVIEW, days-since-release "
        "for OFFER, inverse joining-readiness for PREBOARDING), with a permanent "
        "1.3x ghosting multiplier (BR-03). 404 if the candidate isn't in a "
        "scorable stage or doesn't exist."
    ),
)
def get_drop_risk(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    result = calculate_drop_risk(db, candidate_id, tenant_id)
    if "drop_risk_score" not in result:
        raise HTTPException(status_code=404, detail=f"No drop risk score available for candidate {candidate_id!r} (outcome: {result.get('outcome')}).")
    return DropRiskResponse(candidate_id=candidate_id, **result)
