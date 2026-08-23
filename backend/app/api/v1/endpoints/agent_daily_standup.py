"""Daily standup (8:00 AM EST) and scrum of scrums (8:30 AM EST) endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.agent_daily_standup_service import AgentDailyStandup

router = APIRouter(prefix="/standups", tags=["Daily Standup"])


@router.get("/daily", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_daily_standup(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    8:00 AM EST Daily Standup: Sequential agent reports with validation.

    Each agent reports yesterday's metrics in priority order:
    1. Core recruiting (Thunder, Recruitment Agent, Supervisor)
    2. Resource & allocation
    3. Finance & business
    4. Employee/HR
    5. KPI tracking
    6. Support & engagement
    7. Scoring & decisions

    Every update is validated:
    - Agent marked operational but didn't run → critical
    - Success rate dropped significantly → investigate
    - Abnormally high executions → runaway loop?
    - Log inconsistencies → data integrity?

    Returns: Agent reports + validation issues + CEO focus areas
    """
    try:
        report = await AgentDailyStandup.generate_standup_report(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrum-8-30", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_scrum_of_scrums(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    8:30 AM EST Scrum of Scrums: Flash + CEO + Feedback + Partners (Troy, Curtis).

    Flash is the execution engine. This scrum reviews:
    - Flash's performance (must be 95%+ success)
    - Thunder recruitment metrics (20+ executions/day = 600/month = 7200/year)
    - Partner agent performance (Troy, Curtis)
    - CEO directives (aggressive escalations for any failures)
    - Strategic direction toward $100M/2000 employees

    Flash is accountable for executing all decisions.

    Requires: admin.view (CEO/Super User only)
    """
    # Permission check is enforced via decorator above (require_resource_permission("admin-settings", "view"))
    # No need for hardcoded role check here - removed for zero-hardcoding principle
    try:
        scrum = await AgentDailyStandup.scrum_of_scrums(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return scrum
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
