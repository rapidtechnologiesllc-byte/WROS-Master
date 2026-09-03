"""HTD Pipeline Accountability Agent endpoints."""
from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.htd_pipeline_accountability_agent import HTDPipelineAccountabilityAgent

router = APIRouter(prefix="/htd", tags=["HTD Pipeline Accountability"])


@router.get(
    "/bu/{bu_id}/pipeline",
    dependencies=[Depends(require_resource_permission("hr-pipeline", "view"))]
)
async def get_bu_pipeline(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Deep dive into a BU's SPECIALTYâ†’CORE pipeline.

    Shows:
    - Current CORE headcount (revenue-generating)
    - SPECIALTY in HTD phases (cost center, developing to CORE)
    - Where people are stuck (gate decisions)
    - Conversion forecast (when will they become CORE?)
    - HTD trigger (if pipeline too slow, recommend external hire)

    Used by Flash to coach partners on CORE development.
    """
    try:
        result = await HTDPipelineAccountabilityAgent.track_bu_pipeline(
            tenant_id=current_user.tenant_id,
            bu_id=bu_id,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/partners/conversion-health",
    dependencies=[Depends(require_resource_permission("hr-pipeline", "view"))]
)
async def get_partners_conversion_health(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    CEO View: All partners' SPECIALTYâ†’CORE conversion health.

    Answers:
    - Who's converting well? Who's stuck?
    - Which BUs need HTD to bridge gaps?
    - Total CORE capacity growing on schedule?

    Used by Flash to identify which BUs need support/HTD hiring.
    """
    try:
        result = await HTDPipelineAccountabilityAgent.partners_conversion_health(
            tenant_id=current_user.tenant_id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
