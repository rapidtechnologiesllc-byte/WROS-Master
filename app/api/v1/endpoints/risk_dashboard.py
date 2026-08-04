"""
S-063/HRMS-0463 -- Candidate Risk Dashboard
==================================================================
Prefix: /risk
Tag:    risk-dashboard

GET /risk/dashboard
    Auth: candidate.view -- same read-only recruiter visibility gate
    as S-059/S-060/S-061's dashboards.
POST /risk/dashboard/candidates/{candidate_id}/add-to-queue
    Step 2's "Add to Queue" action. Reuses S-062's real add_to_queue()
    directly -- BR-02's dedup there already covers "if not already
    queued" for free, no separate check needed here.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.recruiter_intervention_queue import PRIORITY_CRITICAL, PRIORITY_HIGH
from app.schemas.risk_dashboard import RiskDashboardResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.intervention_queue_service import add_to_queue
from app.services.risk_dashboard_service import get_risk_dashboard

router = APIRouter(prefix="/risk", tags=["risk-dashboard"])


@router.get("/dashboard", response_model=RiskDashboardResponse, dependencies=[Depends(require_permission("candidate.view"))])
def risk_dashboard(db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    return get_risk_dashboard(db, tenant_id)


@router.post("/dashboard/candidates/{candidate_id}/add-to-queue", dependencies=[Depends(require_permission("candidate.edit"))])
def add_candidate_to_queue(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    risk = db.query(CandidateDropRisk).filter(CandidateDropRisk.tenant_id == tenant_id, CandidateDropRisk.candidate_id == candidate_id).first()
    if risk is None:
        raise HTTPException(status_code=404, detail=f"No drop risk score for candidate {candidate_id!r}.")

    reason = "CRITICAL_DROP_RISK" if risk.risk_level == "CRITICAL" else "HIGH_DROP_RISK"
    priority = PRIORITY_CRITICAL if risk.risk_level == "CRITICAL" else PRIORITY_HIGH
    result = add_to_queue(db, candidate_id, tenant_id, reason, f"{risk.risk_level.title()} Drop Risk: {risk.drop_risk_score}", priority)
    return result
