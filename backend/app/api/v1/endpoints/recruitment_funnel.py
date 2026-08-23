"""
Recruitment Funnel API - Real-time visibility into Phase 1 agent effectiveness.

GET /recruiting/funnel - Complete recruitment pipeline with all 5 pillars
GET /recruiting/funnel/recruitment-only - Just recruitment metrics
GET /recruiting/funnel/resources-only - Just resource health
GET /recruiting/funnel/happiness-only - Just employee happiness
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_recruiter
from app.services.recruitment_funnel_dashboard_service import RecruitmentFunnelDashboard
from app.core.logging import logger

router = APIRouter(prefix="/recruiting", tags=["recruitment-funnel"])


@router.get("/funnel")
async def get_full_recruitment_funnel(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter)
):
    """
    Get complete recruitment funnel showing all 5 pillars:

    RECRUITMENT:
    - Candidates contacted → qualified → interviewed → offered → hired → onboarded
    - Conversion rates at each stage
    - Blockers (where are people stuck?)

    SALES:
    - Pipeline value, deal stages (TBD)

    DELIVERY:
    - Project staffing, utilization (TBD)

    RESOURCE MANAGEMENT:
    - CORE certification, utilization, HTD progress
    - By business unit

    EMPLOYEE HAPPINESS:
    - Retention rate, onboarding completion
    - Target: 95% retention

    Returns: Full funnel with 2030 trajectory analysis
    """
    try:
        funnel = RecruitmentFunnelDashboard.get_full_funnel(
            db=db,
            tenant_id=current_user.tenant_id
        )

        return {
            "status": "success",
            "data": funnel,
            "timestamp": funnel["timestamp"],
            "health": funnel["health_summary"]["overall_health"],
            "priority_action": funnel["health_summary"]["next_action"]
        }

    except Exception as e:
        logger.error(f"Error fetching recruitment funnel: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/funnel/recruitment")
async def get_recruitment_only(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter)
):
    """Get just the recruitment funnel (Phase 1 agents)."""
    try:
        funnel = RecruitmentFunnelDashboard.get_full_funnel(db, current_user.tenant_id)
        return {
            "status": "success",
            "data": funnel["recruitment"],
            "blockers": funnel["recruitment"]["blockers"],
            "health": funnel["recruitment"]["health"]
        }
    except Exception as e:
        logger.error(f"Error fetching recruitment metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funnel/resources")
async def get_resources_only(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter)
):
    """Get resource management metrics (utilization, CORE certification, HTD)."""
    try:
        funnel = RecruitmentFunnelDashboard.get_full_funnel(db, current_user.tenant_id)
        return {
            "status": "success",
            "data": funnel["resources"],
            "health": funnel["resources"]["health"]
        }
    except Exception as e:
        logger.error(f"Error fetching resource metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funnel/happiness")
async def get_happiness_only(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter)
):
    """Get employee happiness metrics (retention, onboarding)."""
    try:
        funnel = RecruitmentFunnelDashboard.get_full_funnel(db, current_user.tenant_id)
        return {
            "status": "success",
            "data": funnel["employee_happiness"],
            "health": funnel["employee_happiness"]["health"]
        }
    except Exception as e:
        logger.error(f"Error fetching happiness metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funnel/2030-trajectory")
async def get_2030_trajectory(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_recruiter)
):
    """
    Calculate if we're on pace to reach 2,000 employees by 2030.

    Returns:
    - Current headcount
    - Target (2,000)
    - Gap
    - Current monthly hire rate vs required rate
    - Projected headcount at current pace
    - On track? (yes/no)
    """
    try:
        funnel = RecruitmentFunnelDashboard.get_full_funnel(db, current_user.tenant_id)
        return {
            "status": "success",
            "data": funnel["progress_2030"],
            "health": funnel["progress_2030"]["health"]
        }
    except Exception as e:
        logger.error(f"Error calculating 2030 trajectory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
