"""Learning Dashboard API - Monitor system autonomous learning health and metrics

Endpoints:
- GET /learning/health - Current system health score
- GET /learning/dashboard - Full learning dashboard data
- GET /learning/orchestrator/{name} - Metrics for specific orchestrator
- GET /learning/outcomes - Recent decision outcomes
- POST /learning/cycle - Manually trigger learning cycle
- GET /learning/recommendations - Current system recommendations
- GET /learning/cross-module - Cross-module insights
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import Users
from app.models.slm_learning_metrics import SLMMetrics
from app.services.unified_learning_orchestrator import UnifiedLearningOrchestrator
from app.services.learning_weight_optimizer import LearningWeightOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/health")
def get_system_health(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get current system health score.

    Returns:
        {
            "health_score": 72.5,
            "status": "good",
            "last_updated": "2026-10-11T15:30:00Z",
            "next_update": "2026-10-11T16:30:00Z"
        }
    """
    try:
        # Get most recent metric
        latest = (
            db.query(SLMMetrics)
            .filter(SLMMetrics.tenant_id == current_user.tenant_id)
            .order_by(SLMMetrics.timestamp.desc())
            .first()
        )

        if not latest:
            return {
                "health_score": 50.0,
                "status": "initializing",
                "message": "System collecting initial metrics",
                "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            }

        # Determine status
        if latest.slm_health_score >= 80:
            status = "excellent"
        elif latest.slm_health_score >= 60:
            status = "good"
        elif latest.slm_health_score >= 40:
            status = "fair"
        else:
            status = "poor"

        return {
            "health_score": latest.slm_health_score,
            "status": status,
            "last_updated": latest.timestamp.isoformat(),
            "operations_processed": latest.operations_processed,
            "weights_updated": latest.learning_weights_updated,
            "cascade_risk": latest.cascade_risk_detected,
            "next_update": (latest.timestamp + timedelta(hours=1)).isoformat(),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
def get_learning_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get complete learning dashboard with trends and recommendations.

    Returns:
        {
            "health_score": 72.5,
            "health_trend": "improving",
            "orchestrators": [
                {
                    "name": "thunder",
                    "accuracy": 0.78,
                    "calibration": "GOOD",
                    "confidence_gap": 0.08
                },
                ...
            ],
            "recent_weight_updates": [...],
            "active_recommendations": [...],
            "cascade_alerts": []
        }
    """
    try:
        dashboard = UnifiedLearningOrchestrator.get_learning_dashboard(
            db, current_user.tenant_id
        )

        return {
            "health_score": dashboard.get("current_health", 50.0),
            "health_trend": dashboard.get("health_trend", "stable"),
            "recent_metrics": dashboard.get("recent_metrics", []),
            "dashboard_generated": datetime.utcnow().isoformat(),
            "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestrator/{name}")
def get_orchestrator_metrics(
    name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get detailed metrics for specific orchestrator (thunder, flash, interview, offer, finance).

    Returns:
        {
            "orchestrator": "thunder",
            "decisions_analyzed": 156,
            "accuracy": 0.78,
            "calibration": "GOOD",
            "confidence_gap": 0.08,
            "channel_effectiveness": {
                "email": 0.85,
                "sms": 0.72,
                "whatsapp": 0.68
            },
            "recent_recommendations": [...]
        }
    """
    if name not in ["thunder", "flash", "interview", "offer", "finance"]:
        raise HTTPException(status_code=400, detail=f"Unknown orchestrator: {name}")

    try:
        analysis = LearningWeightOptimizer.analyze_decision_batch(
            db, current_user.tenant_id, name
        )

        return {
            "orchestrator": name,
            "decisions_analyzed": analysis.get("decisions_analyzed", 0),
            "accuracy": analysis.get("accuracy", 0.0),
            "calibration": analysis.get("calibration_status", "UNKNOWN"),
            "confidence_gap": analysis.get("confidence_gap", 0.0),
            "recommendations": analysis.get("recommendations", []),
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get {name} metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outcomes")
def get_recent_outcomes(
    limit: int = 20,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get recent decision outcomes (predicted vs actual).

    Returns:
        {
            "total_outcomes": 145,
            "recent": [
                {
                    "decision_id": "...",
                    "predicted": "engagement",
                    "predicted_probability": 0.72,
                    "actual": "email_opened",
                    "actual_result": true,
                    "confidence_gap": 0.28,
                    "timestamp": "2026-10-11T15:20:00Z"
                },
                ...
            ]
        }
    """
    try:
        pending = LearningOutcomeTracker.get_pending_outcomes(
            db, datetime.utcnow() - timedelta(days=days)
        )

        return {
            "total_outcomes": pending.get("total_pending", 0),
            "timeframe_days": days,
            "message": "Outcome tracking in development - data structure prepared",
            "ready_for_implementation": True,
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get outcomes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cycle")
def trigger_learning_cycle(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Manually trigger a learning cycle (normally runs automatically every hour).

    Returns:
        {
            "cycle_id": "...",
            "status": "in_progress",
            "orchestrators_analyzed": 5,
            "weights_updated": 2,
            "health_score": 72.5,
            "cascade_detected": false
        }
    """
    try:
        logger.info(f"[LearningAPI] Manual cycle triggered by {current_user.email}")

        cycle_report = UnifiedLearningOrchestrator.run_learning_cycle(
            db, current_user.tenant_id
        )

        return {
            "cycle_status": cycle_report.get("status", "completed"),
            "started_at": cycle_report.get("cycle_start"),
            "completed_at": cycle_report.get("cycle_end"),
            "orchestrators_analyzed": len(
                cycle_report.get("orchestrators_analyzed", [])
            ),
            "weights_updated": len(cycle_report.get("weights_updated", [])),
            "health_score": cycle_report.get("health_score", 50.0),
            "cascade_detected": cycle_report.get("cascade_detected", False),
            "recommendations": cycle_report.get("recommendations", []),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Cycle failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
def get_active_recommendations(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get active system recommendations based on learning analysis.

    Returns:
        {
            "recommendations": [
                {
                    "priority": "HIGH",
                    "type": "accuracy_improvement",
                    "description": "Thunder email accuracy at 72%, target 85%",
                    "action": "Increase email template personalization",
                    "estimated_impact": "+8% accuracy"
                },
                ...
            ]
        }
    """
    try:
        # Get latest cycle report
        latest = (
            db.query(SLMMetrics)
            .filter(SLMMetrics.tenant_id == current_user.tenant_id)
            .order_by(SLMMetrics.timestamp.desc())
            .first()
        )

        if not latest or not latest.slm_recommendation:
            return {"recommendations": []}

        import json

        recs = json.loads(latest.slm_recommendation)

        return {
            "recommendations": recs,
            "count": len(recs),
            "generated_at": latest.timestamp.isoformat(),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cross-module")
def get_cross_module_insights(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get cross-module intelligence insights (Thunder → Flash → Interview → Offer).

    Returns:
        {
            "insights": {
                "thunder_to_flash": [
                    {
                        "learning": "Email works 40% better for tech candidates",
                        "confidence": 0.85,
                        "action": "Prioritize email-responsive candidates"
                    }
                ],
                "flash_to_interview": [...],
                "interview_to_offer": [...],
                "offer_to_finance": [...]
            }
        }
    """
    try:
        # This will be populated by the learning cycle
        return {
            "insights": {
                "thunder_to_flash": [],
                "flash_to_interview": [],
                "interview_to_offer": [],
                "offer_to_finance": [],
            },
            "note": "Cross-module insights populated during learning cycles",
            "next_update": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

    except Exception as e:
        logger.error(f"[LearningAPI] Failed to get insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import at bottom to avoid circular imports
from app.services.learning_outcome_tracker import LearningOutcomeTracker
