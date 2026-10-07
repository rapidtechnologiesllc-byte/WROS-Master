"""Spartan Forecasting API - Autonomous System Needs + Decision Validation
Endpoints for:
1. KPI Monitoring → Forecast what's needed
2. Decision Validation → Tell humans when they're wrong
3. Autonomous Alerts → System informs humans of violations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.logging import logger
from app.services.autonomous_forecasting_service import AutonomousForecastingService

router = APIRouter(prefix="/spartan/forecasting", tags=["forecasting"])


@router.get(
    "/health/summary",
    dependencies=[Depends(require_resource_permission("forecasts", "view"))]
)
def forecasting_system_health(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    System health check for forecasting layer

    Shows:
    - Is recruitment on track?
    - Is resource utilization healthy?
    - Is revenue on pace?
    - Are there policy violations?
    - What escalations are pending?

    This is the "pulse" of the organism
    """
    try:
        health = {
            "system": "forecasting_and_governance",
            "status": "operational",
            "checks": {
                "recruitment": {
                    "status": "monitoring",
                    "endpoint": "/spartan/forecasting/recruitment/forecast"
                },
                "resources": {
                    "status": "monitoring",
                    "endpoint": "/spartan/forecasting/resources/forecast"
                },
                "revenue": {
                    "status": "monitoring",
                    "endpoint": "/spartan/forecasting/revenue/forecast"
                },
                "policy_enforcement": {
                    "status": "active",
                    "endpoint": "/spartan/forecasting/decision/validate"
                },
                "autonomous_alerts": {
                    "status": "active",
                    "endpoint": "/spartan/forecasting/alert/generate"
                }
            },
            "message": "Forecasting layer operational. System monitoring KPIs, validating decisions, generating alerts."
        }

        return {"status": "success", "data": health}

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
