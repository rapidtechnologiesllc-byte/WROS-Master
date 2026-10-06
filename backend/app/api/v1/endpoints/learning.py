"""Learning Metrics & Recommendations API Endpoints

Provides REST API for:
1. SLM health score and metrics dashboard
2. Thunder outreach recommendations
3. Flash job matching strategy
4. Learning performance analytics
"""
import logging
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.slm_learning_framework import SLMlearningFramework
from app.services.thunder_learning_module import ThunderLearningModule
from app.services.flash_learning_module import FlashLearningModule
from app.core.security import require_role_template_permission
from app.core.permission_registry import Permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get(
    "/health",
    summary="Get SLM Health Score",
    description="Get composite SLM health score with component breakdown",
)
async def get_slm_health_score(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get current SLM health score (0-100%).

    Returns composite health across:
    - Thunder outreach effectiveness
    - Flash job matching quality
    - Interview conversion rates
    - Offer acceptance rates

    Cascade risk flagged if score < 70%.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = SLMlearningFramework.compute_slm_health_score(db, tenant_id)
        if not isinstance(result, dict) or "slm_health_score" not in result:
            raise HTTPException(status_code=500, detail="Failed to compute health score")

        return {
            "status": "success",
            "slm_health_score": result.get("slm_health_score", 0),
            "components": result.get("components", {}),
            "cascade_risk": result.get("cascade_risk_detected", False),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        }

    except Exception as e:
        logger.error(f"Failed to get SLM health score: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get health score: {str(e)}")


@router.post(
    "/update-weights",
    summary="Update Learning Weights",
    description="Force update of learning weights based on recent metrics",
)
async def update_learning_weights(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Trigger learning weight update (normally happens every 50 operations).
    Recalculates optimal channels, timings, and strategies based on latest metrics.

    Returns summary of changes applied.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = SLMlearningFramework.update_learning_weights(db, tenant_id)
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to update learning weights")

        return {
            "status": "success",
            "update_summary": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to update learning weights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update weights: {str(e)}")


@router.get(
    "/thunder/recommendations",
    summary="Get Thunder Outreach Recommendations",
    description="Get recommended outreach strategy for candidate based on learning",
)
async def get_thunder_recommendations(
    candidate_id: str = Query(..., description="Candidate ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get Thunder's recommended outreach strategy for a specific candidate.

    Returns:
    - Recommended channel (email, SMS, WhatsApp, LinkedIn)
    - Optimal timing (hour of day, day of week)
    - Message template (personalized by profile)
    - Confidence score

    Based on learning from 50+ similar candidates.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = ThunderLearningModule.get_recommended_outreach_strategy(
            db=db,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
        )
        if not isinstance(result, dict) or "strategy" not in result:
            raise HTTPException(status_code=500, detail="Failed to get recommendations")

        return {
            "status": "success",
            "recommendations": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to get Thunder recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get(
    "/thunder/channel-effectiveness",
    summary="Get Channel Effectiveness Report",
    description="Show which outreach channels work best overall and by profile",
)
async def get_channel_effectiveness(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get report on channel effectiveness across all candidates.

    Returns ranked list of channels by success rate with confidence scores.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = ThunderLearningModule.get_channel_effectiveness_report(
            db=db,
            tenant_id=tenant_id,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to get effectiveness report")

        return {
            "status": "success",
            "report": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to get effectiveness report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")


@router.get(
    "/thunder/optimal-contact-window",
    summary="Detect Optimal Contact Window",
    description="Determine best time to contact candidates (hour + day)",
)
async def get_optimal_contact_window(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get optimal time to contact candidates based on response patterns.

    Returns hour of day and day of week when candidates are most responsive.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = ThunderLearningModule.detect_optimal_contact_window(
            db=db,
            tenant_id=tenant_id,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to detect contact window")

        return {
            "status": "success",
            "contact_window": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to detect contact window: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to detect window: {str(e)}")


@router.get(
    "/flash/job-strategy",
    summary="Get Job Matching Strategy",
    description="Get Flash recommendations for job matching based on learning",
)
async def get_job_matching_strategy(
    job_id: str = Query(..., description="Job ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get Flash's job matching strategy based on learning from this job.

    Returns:
    - Top candidate profile characteristics
    - Expected interview → offer conversion rate
    - Expected offer acceptance rate
    - Optimal interview scheduling timing
    - Recommended salary range and offer strategy
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = FlashLearningModule.get_job_matching_strategy(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to get job strategy")

        return {
            "status": "success",
            "strategy": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to get job strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {str(e)}")


@router.get(
    "/flash/interview-insights",
    summary="Get Interview Scheduling Insights",
    description="Learn optimal interview timing based on show-up rates",
)
async def get_interview_insights(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get insights on optimal interview scheduling.

    Returns:
    - Average candidate show-up rate
    - Optimal days from application to interview
    - Confidence score based on data size
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = FlashLearningModule.get_interview_scheduling_insights(
            db=db,
            tenant_id=tenant_id,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to get interview insights")

        return {
            "status": "success",
            "insights": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to get interview insights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")


@router.get(
    "/flash/offer-strategy",
    summary="Get Offer Generation Strategy",
    description="Learn what offer terms work best for a specific job",
)
async def get_offer_strategy(
    job_id: str = Query(..., description="Job ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get offer generation strategy for a specific job.

    Returns:
    - Typical salary range for successful offers
    - Expected offer acceptance rate
    - Average negotiation rounds required
    - Recommended offer strategy (aggressive, standard, conservative)
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = FlashLearningModule.get_offer_generation_strategy(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to get offer strategy")

        return {
            "status": "success",
            "strategy": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to get offer strategy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {str(e)}")


@router.post(
    "/thunder/record-engagement",
    summary="Record Thunder Engagement Result",
    description="Record candidate engagement result after outreach attempt",
)
async def record_engagement(
    candidate_id: str = Query(..., description="Candidate ID"),
    channel: str = Query(..., description="Outreach channel (email, sms, whatsapp, linkedin)"),
    engagement_type: str = Query(..., description="Type of engagement (opened, clicked, replied, engaged)"),
    response_time_hours: float = Query(None, description="Hours to response"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Record how candidate engaged with Thunder outreach.
    Updates learning model to improve future recommendations.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = ThunderLearningModule.record_engagement_result(
            db=db,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            channel=channel,
            engagement_type=engagement_type,
            response_time_hours=response_time_hours,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to record engagement")

        return {
            "status": "success",
            "result": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to record engagement: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record: {str(e)}")


@router.post(
    "/flash/record-interview",
    summary="Record Flash Interview Result",
    description="Record interview completion and result",
)
async def record_interview(
    job_id: str = Query(..., description="Job ID"),
    success: bool = Query(..., description="Did interview happen successfully?"),
    attended: bool = Query(True, description="Did candidate attend?"),
    feedback_score: float = Query(None, description="Interviewer feedback (0-100)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Record interview result. Updates Flash learning about optimal interview timing.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = FlashLearningModule.record_interview_result(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
            success=success,
            attended=attended,
            feedback_score=feedback_score,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to record interview")

        return {
            "status": "success",
            "result": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to record interview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record: {str(e)}")


@router.post(
    "/flash/record-offer",
    summary="Record Flash Offer Result",
    description="Record offer generation and acceptance",
)
async def record_offer(
    job_id: str = Query(..., description="Job ID"),
    offer_extended: bool = Query(..., description="Was offer extended?"),
    offer_accepted: bool = Query(None, description="Was offer accepted?"),
    salary_offered: float = Query(None, description="Offered salary"),
    salary_expected: float = Query(None, description="Candidate expected salary"),
    negotiation_rounds: int = Query(0, description="Negotiation rounds"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Record offer result. Updates Flash learning about what terms work best.
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = str(current_user.tenant_id)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = FlashLearningModule.record_offer_result(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
            offer_extended=offer_extended,
            offer_accepted=offer_accepted,
            salary_offered=salary_offered,
            salary_expected=salary_expected,
            negotiation_rounds=negotiation_rounds,
        )
        if not isinstance(result, dict):
            raise HTTPException(status_code=500, detail="Failed to record offer")

        return {
            "status": "success",
            "result": result or {},
        }

    except Exception as e:
        logger.error(f"Failed to record offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record: {str(e)}")
