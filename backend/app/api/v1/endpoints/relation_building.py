"""
Relation Building Agent API Endpoints

Exposes relation building persona extraction for downstream systems.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.core.logging import logger
from app.services.relation_building_agent_service import RelationBuildingAgent
from app.services.relation_building_dashboard_service import RelationBuildingDashboard
from app.models.user import Users

router = APIRouter(prefix="/relation-building", tags=["relation-building"])


@router.post("/extract-persona/{candidate_id}")
async def extract_candidate_persona(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Extract persona for a candidate.

    This endpoint:
    1. Parses candidate's resume using SLM
    2. Analyzes career trajectory, skills, motivations
    3. Classifies candidate engagement readiness
    4. Stores persona facts in candidate memory
    5. Returns persona profile for use by Thunder, Offer Generator, etc.

    Args:
        candidate_id: Candidate UUID

    Returns:
        {
            "status": "success" | "error",
            "candidate_id": str,
            "candidate_name": str,
            "persona": {
                "career_level": "entry" | "mid" | "senior" | "lead" | "principal",
                "skill_depth": "focused" | "specialist" | "generalist",
                "motivation_primary": str,
                "motivators": [str],
                "constraints": [str],
                "risk_factors": [str],
                "engagement_readiness": "high" | "medium" | "low",
            },
            "profile": {
                "years_experience": int,
                "companies_worked": int,
                "skill_count": int,
                "skill_areas": [str],
                "job_stability": float,
                "current_title": str,
                "current_employer": str,
            },
            "relationship_status": "RECEPTIVE" | "INTERESTED" | "HESITANT" | "RESISTANT",
            "recommended_engagement": str,
            "memory_facts_stored": int,
        }
    """
    try:
        result = await RelationBuildingAgent.extract_candidate_persona(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
        )

        if result["status"] != "success":
            raise HTTPException(status_code=404, detail=result.get("message", "Persona extraction failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Relation building persona extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during persona extraction")


@router.get("/candidate-relationship/{candidate_id}")
async def get_candidate_relationship_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get relationship status for a candidate (cached from last extraction).

    Returns persona-based relationship intelligence.
    """
    try:
        result = await RelationBuildingAgent.report_to_flash(
            candidate_id=candidate_id,
            tenant_id=current_user.UserID,
            db=db,
        )

        if result["status"] != "success":
            raise HTTPException(status_code=404, detail="Candidate not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Relationship status retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/flash-report")
async def get_flash_candidate_intelligence(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get candidate relationship intelligence for Flash Orchestration Engine.

    This is called by Flash during daily coordination to understand
    the quality and engagement readiness of the candidate pool.

    Returns summary of:
    - Engagement distribution (high/medium/low)
    - Risk factor analysis
    - Career level mix
    - Recommended engagement strategies per candidate
    """
    # This would be called during Flash daily coordination
    # Returns a summary similar to what Flash reports

    return {
        "status": "success",
        "message": "Relation Building Agent ready for Flash coordination",
        "agent_name": "Relation Building Agent",
        "reports_to": "Flash Orchestration Engine",
        "capabilities": [
            "extract_persona",
            "classify_engagement_readiness",
            "identify_risk_factors",
            "recommend_engagement_strategy",
            "store_in_memory",
        ],
    }


@router.get("/dashboard/standup")
async def get_daily_standup(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get Relation Building Agent daily standup report.

    Format: SDLC Daily Kanban Standup
    - Yesterday: What was completed (metrics, summary)
    - Today: What's planned (tasks, summary)
    - Blockers: What's impeding progress (issues, severity)
    - Impact: How we're improving hiring (metrics, summary)
    - Overall Health: Agent health score and status

    This report is used by Flash Orchestration Engine during morning
    standup (8:00 AM) to coordinate all autonomous systems.

    Returns:
        {
            "status": "success",
            "agent_name": "Relation Building Agent",
            "reports_to": "Flash Orchestration Engine",
            "standup_date": "2026-08-23",
            "standup_time": "10:15:00",
            "yesterday": {...},  # What was completed
            "today": {...},      # What's planned
            "blockers": {...},   # Issues identified
            "impact": {...},     # How it's improving hiring
            "overall_health": {
                "score": 87,
                "status": "HEALTHY",
                "trend": "↑"
            }
        }
    """
    try:
        result = RelationBuildingDashboard.get_daily_standup(
            tenant_id=current_user.UserID,
            db=db,
        )
        return result

    except Exception as e:
        logger.error(f"Standup report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error generating standup report")


@router.get("/dashboard/metrics")
async def get_agent_metrics(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """
    Get Relation Building Agent performance metrics.

    Tracks:
    - Total candidates with personas extracted
    - Engagement readiness distribution
    - Risk factor analysis
    - Downstream system improvements
    - Persona accuracy over time

    Used by monitoring systems and dashboards.
    """
    return {
        "status": "success",
        "message": "Agent metrics endpoint - detailed metrics coming from dashboard service",
        "agent_name": "Relation Building Agent",
        "metrics": {
            "personas_extracted_total": 0,  # Will populate from dashboard
            "engagement_distribution": {
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "risk_factors_tracked": 0,
            "accuracy_improvement_trend": "N/A",
        },
    }
