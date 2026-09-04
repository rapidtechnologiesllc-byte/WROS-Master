"""
S-070/HRMS-0470 -- Candidate Engagement Health Metrics
==================================================================
Prefix: /candidates
import logging
Tag:    engagement-metrics

GET /candidates/{candidate_id}/engagement-metrics
    Auth: candidate.view -- same read-only recruiter visibility gate
    as S-059/S-060's dashboards. Recalculates fresh on every read (same
    on-demand posture as S-053/S-060), in addition to the 4-hour job.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.schemas.engagement_metrics import EngagementMetricsResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.engagement_metrics_service import calculate_engagement_health

router = APIRouter(tags=["engagement-metrics"])

@router.get(
    "/candidates/{candidate_id}/engagement-metrics",
    response_model=EngagementMetricsResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a candidate's engagement health metrics (S-070/HRMS-0470)",
)
def get_engagement_metrics(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id()
    result = calculate_engagement_health(db, candidate_id, tenant_id)
    if result.get("outcome") != "calculated":
        raise HTTPException(status_code=404, detail=f"No engagement metrics available for candidate {candidate_id!r} (outcome: {result.get('outcome')}).")
    return EngagementMetricsResponse(candidate_id=candidate_id, **{k: v for k, v in result.items() if k != "outcome"})
