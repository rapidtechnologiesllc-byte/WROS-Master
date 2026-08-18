"""Daily standup and scrum of scrums endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission)
from app.core.database import get_db
from app.models.user import Users
from app.services.agent_standups_service import AgentStandupsCoordinator

router = APIRouter(prefix="/standups", tags=["Agent Standups"])


@router.get("/daily-report", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_daily_standup_report(
    agent: str = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get daily standup report for all agents or specific agent.

    6:00 AM IST: All agents report daily metrics to their managers.
    Reports: Executions, success rate, duration, alerts/blockers.

    Requires: admin.view (CEO, Super User)
    """
    try:
        report = await AgentStandupsCoordinator.generate_daily_standup_report(
            tenant_id=current_user.tenant_id,
            db=db,
            agent_name=agent
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrum-of-scrums", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_scrum_of_scrums(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Scrum of Scrums: Thunder + Flask report to CEO Agent.

    7:00 AM IST: Thunder (recruitment) + Flask (operations) sync with CEO Agent.
    CEO Agent reviews metrics and aggressively manages underperformers:
    - Escalate/replace agents <75% success rate
    - Emergency restart agents with 0 executions
    - Strategic decisions for 2000 employee target

    Requires: admin.view (CEO, Super User only)
    """
    try:
        # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "view"))
        scrum = await AgentStandupsCoordinator.scrum_of_scrums(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return scrum
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly-feedback", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_weekly_feedback(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Weekly Feedback Session: Feedback Agent reviews all agents.

    Friday 5:00 PM IST: Each agent receives performance feedback including:
    - Performance score (0-100)
    - Success rate, execution count, speed metrics
    - Recognition for top performers (90+)
    - Improvement plans for underperformers (<75)
    - Final warnings / replacement decisions (<50)

    Requires: admin.view (CEO/Super User)
    """
    try:
        feedback = await AgentStandupsCoordinator.weekly_feedback_session(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return feedback
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
