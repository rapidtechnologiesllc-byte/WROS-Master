"""
SLM Analytics Endpoints - Decision tracking, metrics, and business impact analysis

Provides visibility into Specialized Language Model decisions with:
- Confidence score distributions
- Escalation patterns and rates
- Business impact metrics (cost, hiring velocity)
- 90-day validation outcomes
- Decision trends over time
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.slm_decision import SLMDecision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slm", tags=["SLM Analytics"])


def get_time_range(time_range: str = "24h"):
    """Calculate start time based on time range string."""
    now = datetime.utcnow()
    if time_range == "1h":
        return now - timedelta(hours=1)
    elif time_range == "24h":
        return now - timedelta(hours=24)
    elif time_range == "7d":
        return now - timedelta(days=7)
    elif time_range == "30d":
        return now - timedelta(days=30)
    return now - timedelta(hours=24)  # Default 24h


@router.get("/metrics", dependencies=[Depends(require_resource_permission("slm-training-data", "view"))])
def get_slm_metrics(time_range: str = Query("24h"), db: Session = Depends(get_db)):
    """
    Get SLM decision metrics for the specified time range.

    Returns:
    {
        "last_24h": {
            "total_decisions": 847,
            "escalations": 12,
            "escalation_rate": 0.014,
            "avg_confidence": 0.87,
            "candidates_affected": 156
        },
        "by_message_type": {
            "job_created_flash": {"decisions": 234, "escalations": 3},
            "offer_generated": {"decisions": 156, "escalations": 8},
            ...
        },
        "business_impact": {
            "total_cost": 2300000,
            "hiring_velocity_impact": 0.92,
            "validation_pending": 45
        }
    }
    """
    start_time = get_time_range(time_range)

    # Total decisions in time range
    total_query = db.query(SLMDecision).filter(SLMDecision.created_at >= start_time)
    total_decisions = total_query.count()
    escalations = total_query.filter(SLMDecision.was_escalated == True).count()

    # Confidence scores
    confidence_results = db.query(func.avg(SLMDecision.slm_confidence)).filter(
        SLMDecision.created_at >= start_time
    ).scalar()
    avg_confidence = confidence_results or 0.0

    # Breakdown by message type
    by_type = (
        db.query(
            SLMDecision.message_type,
            func.count(SLMDecision.id).label("decisions"),
            func.sum(func.cast(SLMDecision.was_escalated, db.Integer)).label("escalations")
        )
        .filter(SLMDecision.created_at >= start_time)
        .group_by(SLMDecision.message_type)
        .all()
    )

    by_message_type = {
        row[0]: {
            "decisions": row[1],
            "escalations": row[2] or 0
        }
        for row in by_type
    }

    # Business impact summary
    total_cost = 0
    candidates_affected = 0
    validation_pending = total_query.filter(SLMDecision.validated_at == None).count()

    # Count unique candidates affected (from business_impact JSON)
    try:
        affected_query = db.query(func.count(func.distinct(SLMDecision.id))).filter(
            and_(
                SLMDecision.created_at >= start_time,
                SLMDecision.business_impact.isnot(None)
            )
        ).scalar()
        candidates_affected = affected_query or 0
    except Exception as e:
        logger.warning(f"Failed to calculate candidates affected: {e}")

    return {
        "time_range": time_range,
        "last_24h": {
            "total_decisions": total_decisions,
            "escalations": escalations,
            "escalation_rate": escalations / total_decisions if total_decisions > 0 else 0,
            "avg_confidence": float(avg_confidence),
            "candidates_affected": candidates_affected
        },
        "by_message_type": by_message_type,
        "business_impact": {
            "total_cost": total_cost,
            "hiring_velocity_impact": 0.92,  # Placeholder - calculate from data
            "validation_pending": validation_pending
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/decisions", dependencies=[Depends(require_resource_permission("slm-training-data", "view"))])
def get_slm_decisions(
    limit: int = Query(50, ge=1, le=500),
    time_range: str = Query("24h"),
    message_type: str = Query("", description="Filter by message type"),
    escalated_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Get recent SLM decisions with optional filtering.

    Returns array of SLMDecision records with full details.
    """
    start_time = get_time_range(time_range)

    query = db.query(SLMDecision).filter(SLMDecision.created_at >= start_time)

    if message_type:
        query = query.filter(SLMDecision.message_type == message_type)

    if escalated_only:
        query = query.filter(SLMDecision.was_escalated == True)

    decisions = query.order_by(SLMDecision.created_at.desc()).limit(limit).all()

    return {
        "decisions": [
            {
                "id": str(d.id),
                "message_type": d.message_type,
                "message_id": str(d.message_id),
                "slm_confidence": d.slm_confidence,
                "risk_level": d.risk_level,
                "was_escalated": d.was_escalated,
                "escalation_reason": d.escalation_reason,
                "reasoning": d.slm_analysis.get("reasoning") if d.slm_analysis else None,
                "business_impact": d.business_impact,
                "validation_plan": d.validation_plan,
                "analysis_at": d.analysis_at.isoformat() if d.analysis_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
        "total": db.query(SLMDecision).filter(SLMDecision.created_at >= start_time).count(),
        "time_range": time_range
    }


@router.get("/escalation-patterns", dependencies=[Depends(require_resource_permission("slm-training-data", "view"))])
def get_escalation_patterns(db: Session = Depends(get_db)):
    """
    Identify why decisions are being escalated.

    Returns breakdown of escalation reasons by frequency.
    """
    patterns = (
        db.query(
            SLMDecision.escalation_reason,
            func.count(SLMDecision.id).label("count")
        )
        .filter(SLMDecision.was_escalated == True)
        .group_by(SLMDecision.escalation_reason)
        .order_by(func.count(SLMDecision.id).desc())
        .limit(20)
        .all()
    )

    return {
        "patterns": [
            {
                "reason": row[0],
                "count": row[1]
            }
            for row in patterns
        ]
    }


@router.get("/validation-outcomes", dependencies=[Depends(require_resource_permission("slm-training-data", "view"))])
def get_validation_outcomes(days: int = Query(90), db: Session = Depends(get_db)):
    """
    Get 90-day validation outcomes for past decisions.

    Returns success rate and outcome distribution.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Decisions with validation completed
    validated = db.query(SLMDecision).filter(
        and_(
            SLMDecision.validated_at.isnot(None),
            SLMDecision.created_at >= cutoff_date
        )
    ).count()

    # Still pending validation
    pending = db.query(SLMDecision).filter(
        and_(
            SLMDecision.validated_at == None,
            SLMDecision.created_at >= cutoff_date
        )
    ).count()

    return {
        "validation_period_days": days,
        "validated_count": validated,
        "pending_count": pending,
        "validation_rate": validated / (validated + pending) if (validated + pending) > 0 else 0,
        "cutoff_date": cutoff_date.isoformat()
    }
