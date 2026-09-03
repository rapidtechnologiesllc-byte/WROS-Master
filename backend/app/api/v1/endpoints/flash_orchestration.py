from app.core.logging import logger
"""Flash Orchestration Engine endpoints - Daily command coordination."""
from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.flash_orchestration_engine import FlashOrchestrationEngine

router = APIRouter(prefix="/flash", tags=["Flash Orchestration"])


@router.get(
    "/daily-coordination",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))]
)
async def get_daily_coordination(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Flash's daily coordination engine.

    Analyzes:
    1. HTD Pipeline health (SPECIALTYâ†’CORE conversion by partner)
    2. Opportunity health (sales pipeline, stalled deals)
    3. Agent state (performance of recruiting/resource agents)

    Identifies bottlenecks:
    - No development pipeline (hire external CORE)
    - CORE deficit (too few certified, forecast too low)
    - Stalled deals (likely due to staffing gaps)
    - Agent underperformance (if recruiters/resource team failing)

    Issues directives to partners on what to do TODAY.
    Escalates to CEO if critical.

    Used by:
    - Admin dashboard (view daily directives)
    - Scrum of Scrums (Flash reports to CEO)
    - Partner success agent (coaching based on directives)
    """
    try:
        result = await FlashOrchestrationEngine.daily_flash_coordination(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
