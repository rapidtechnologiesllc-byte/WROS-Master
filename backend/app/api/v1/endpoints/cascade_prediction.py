"""
Cascade Success Prediction - Master Intelligence Endpoint
Predicts total probability of success from contact → offer acceptance → 6-month retention.

This endpoint combines all 5 module predictions into a single probability that shows:
- Will this candidate succeed across the entire hiring journey?
- What are the critical bottlenecks?
- What actions should we take?

Routes:
  GET /cascade-predictions/{candidate_id}/{job_id}
  POST /cascade-predictions/evaluate - Bulk evaluate candidates
"""

from typing import Dict, List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.candidate import Candidate
from app.models.user import Jobs
from app.services.cross_module_intelligence import CrossModuleIntelligence
from app.core.logging import logger

router = APIRouter(prefix="/cascade-predictions", tags=["cascade-prediction"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────────────────────

class CascadePredictionRequest(BaseModel):
    """Request for cascade success prediction."""
    candidate_id: str
    job_id: str
    override_confidence: Optional[float] = None  # For testing


class CascadePredictionResponse(BaseModel):
    """Complete cascade success prediction with all details."""
    cascade_success_probability: float  # 0.0-1.0, e.g., 0.24 (24%)
    thunder_probability: float  # Engagement rate
    flash_probability: float  # Fit score
    interview_probability: float  # Pass rate
    offer_probability: float  # Acceptance rate
    employee_probability: float  # 6-month retention
    recommendation: str  # RECOMMEND, PROCEED_WITH_CAUTION, NOT_RECOMMENDED
    critical_risks: List[str]
    bottleneck: str  # Which module is most constrained?
    actions_recommended: List[str]
    confidence_score: float  # System confidence in this prediction (0-1)
    details: Dict


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{candidate_id}/{job_id}",
    response_model=CascadePredictionResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get cascade success prediction for candidate + job",
)
def get_cascade_prediction(
    candidate_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Predict likelihood of success for candidate on this job.

    The prediction combines:
    1. Thunder: Will candidate engage with our outreach? (email/SMS/WhatsApp response)
    2. Flash: Does candidate match the job requirements? (fit, qualifications)
    3. Interview: Will candidate pass interviews? (assessment results)
    4. Offer: Will candidate accept our offer? (salary expectations, decision timeline)
    5. Employee: Will candidate stay 6+ months? (retention risk factors)

    Cascade probability = Thunder × Flash × Interview × Offer × Employee

    Example:
    - Thunder: 65% (candidate engagement rate for this segment)
    - Flash: 82% (fit score for job type)
    - Interview: 78% (pass rate for role level)
    - Offer: 72% (acceptance rate at current salary range)
    - Employee: 88% (retention rate for this BU)
    - Cascade: 0.65 × 0.82 × 0.78 × 0.72 × 0.88 = 24% total success

    Recommendation:
    - 0.40+: RECOMMEND (high confidence path)
    - 0.20-0.40: PROCEED_WITH_CAUTION (needs specific actions)
    - 0.00-0.20: NOT_RECOMMENDED (critical risks, escalate)
    """
    try:
        # Fetch candidate and job
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == current_user.tenant_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        job = db.query(Jobs).filter(
            Jobs.jobID == job_id,
            Jobs.tenant_id == current_user.tenant_id
        ).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Infer segments for prediction
        candidate_segment = CrossModuleIntelligence._infer_candidate_segment(candidate)
        job_segment = CrossModuleIntelligence._infer_job_segment(job)

        # Get cascade prediction
        prediction = CrossModuleIntelligence.get_cascade_success_prediction(
            db=db,
            tenant_id=current_user.tenant_id,
            candidate_segment=candidate_segment,
            job_type=job_segment
        )

        return CascadePredictionResponse(
            cascade_success_probability=prediction.get("cascade_success_probability", 0.0),
            thunder_probability=prediction.get("thunder_probability", 0.0),
            flash_probability=prediction.get("flash_probability", 0.0),
            interview_probability=prediction.get("interview_probability", 0.0),
            offer_probability=prediction.get("offer_probability", 0.0),
            employee_probability=prediction.get("employee_probability", 0.0),
            recommendation=prediction.get("recommendation", "UNKNOWN"),
            critical_risks=prediction.get("critical_risks", []),
            bottleneck=prediction.get("bottleneck", "unknown"),
            actions_recommended=prediction.get("actions_recommended", []),
            confidence_score=prediction.get("confidence", 0.5),
            details=prediction,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CascadePrediction] Error getting prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute cascade prediction")


@router.post(
    "/evaluate",
    response_model=List[CascadePredictionResponse],
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Bulk evaluate cascade predictions for candidates",
)
def bulk_evaluate_predictions(
    requests: List[CascadePredictionRequest],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Evaluate cascade success probability for multiple candidate+job pairs.

    Useful for:
    - Ranking candidates for a job opening
    - Identifying candidates who will likely accept offers
    - Predicting who will stay 6+ months
    - Resource allocation (assign to high-probability opportunities)

    Returns sorted by cascade_success_probability (highest first).
    """
    results = []

    try:
        for req in requests:
            try:
                candidate = db.query(Candidate).filter(
                    Candidate.candidateID == req.candidate_id,
                    Candidate.tenant_id == current_user.tenant_id
                ).first()

                if not candidate:
                    logger.warning(f"[CascadePrediction] Candidate {req.candidate_id} not found")
                    continue

                job = db.query(Jobs).filter(
                    Jobs.jobID == req.job_id,
                    Jobs.tenant_id == current_user.tenant_id
                ).first()

                if not job:
                    logger.warning(f"[CascadePrediction] Job {req.job_id} not found")
                    continue

                # Get prediction
                candidate_segment = CrossModuleIntelligence._infer_candidate_segment(candidate)
                job_segment = CrossModuleIntelligence._infer_job_segment(job)

                prediction = CrossModuleIntelligence.get_cascade_success_prediction(
                    db=db,
                    tenant_id=current_user.tenant_id,
                    candidate_segment=candidate_segment,
                    job_type=job_segment
                )

                results.append(CascadePredictionResponse(
                    cascade_success_probability=prediction.get("cascade_success_probability", 0.0),
                    thunder_probability=prediction.get("thunder_probability", 0.0),
                    flash_probability=prediction.get("flash_probability", 0.0),
                    interview_probability=prediction.get("interview_probability", 0.0),
                    offer_probability=prediction.get("offer_probability", 0.0),
                    employee_probability=prediction.get("employee_probability", 0.0),
                    recommendation=prediction.get("recommendation", "UNKNOWN"),
                    critical_risks=prediction.get("critical_risks", []),
                    bottleneck=prediction.get("bottleneck", "unknown"),
                    actions_recommended=prediction.get("actions_recommended", []),
                    confidence_score=prediction.get("confidence", 0.5),
                    details=prediction,
                ))

            except Exception as e:
                logger.error(f"[CascadePrediction] Error evaluating {req.candidate_id}/{req.job_id}: {e}")
                continue

        # Sort by success probability (highest first)
        results.sort(key=lambda x: x.cascade_success_probability, reverse=True)

        return results

    except Exception as e:
        logger.error(f"[CascadePrediction] Bulk evaluation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Bulk evaluation failed")
