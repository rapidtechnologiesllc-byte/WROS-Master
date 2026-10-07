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


