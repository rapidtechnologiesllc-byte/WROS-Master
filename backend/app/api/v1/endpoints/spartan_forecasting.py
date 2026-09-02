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
from app.core.logging import logger
from app.services.autonomous_forecasting_service import AutonomousForecastingService

router = APIRouter(prefix="/spartan/forecasting", tags=["forecasting"])

@router.post("/recruitment/forecast")
    dependencies=[Depends(require_resource_permission("recruitment", "create"))]
def forecast_recruitment_needs(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Monitor recruitment KPIs and forecast what's needed

    Returns:
    - Current candidates sourced vs target
    - Gap analysis
    - Resource options (more budget, more recruiters, delay timeline)
    - Escalation recommendation
    """
    try:
        forecast = AutonomousForecastingService.forecast_recruitment_needs(db)
        return {"status": "success", "data": forecast}
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Recruitment forecasting failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/forecast")
    dependencies=[Depends(require_resource_permission("resource", "create"))]
def forecast_resource_needs(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Monitor resource utilization and forecast headcount needs

    Returns:
    - Current utilization % vs target 85%
    - Demand fulfillment %
    - Gap analysis
    - Resource options (hire, reduce demand, increase target)
    """
    try:
        forecast = AutonomousForecastingService.forecast_resource_needs(db)
        return {"status": "success", "data": forecast}
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Resource forecasting failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revenue/forecast")
    dependencies=[Depends(require_resource_permission("revenue", "create"))]
def forecast_revenue_needs(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Forecast revenue needs based on burn rate and quarterly targets

    NOTE: Acquisition is PROACTIVE (always hunting for clients every 2 weeks)
    This endpoint forecasts WHAT revenue is needed to stay healthy

    Returns:
    - Revenue gap vs target
    - Months of runway
    - Revenue options (land Fortune 500s, expand existing, raise pricing)
    - Escalation to CRO
    """
    try:
        forecast = AutonomousForecastingService.forecast_revenue_needs(db)
        return {"status": "success", "data": forecast}
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Revenue forecasting failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decision/validate")
    dependencies=[Depends(require_resource_permission("decision", "create"))]
def validate_decision(
    decision_type: str,  # "APPROVE_PROPOSAL", "ADJUST_TIMELINE", "HIRE", "SET_PRICING"
    parameters: Dict[str, Any],  # Decision-specific params (margin_percent, delay_days, etc.)
    decision_maker_id: str,  # Who is making this decision
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate a human decision against system policies

    When a human makes a decision, system checks if it violates constraints:
    - Margin floor policy: Can't approve proposals below 30% margin
    - Max delay policy: Can't delay project >14 days without approval
    - Utilization ceiling: Can't allocate if >85% utilization
    - Revenue policy: Can't reduce pricing below breakeven

    Returns:
    - APPROVED (no policy violations)
    - POLICY_VIOLATION with severity CRITICAL/HIGH/MEDIUM
    - Override information (who can override, justification required)

    Example:
      CFO tries: {"type": "APPROVE_PROPOSAL", "parameters": {"margin_percent": 25}}
      System: REJECTED - "Violates MARGIN_FLOOR policy (30% minimum)"
    """
    try:
        decision = {
            "type": decision_type,
            "parameters": parameters
        }

        validation = AutonomousForecastingService.validate_decision_against_policy(
            db, decision, decision_maker_id
        )

        return {"status": "success", "data": validation}

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Decision validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert/generate")
    dependencies=[Depends(require_resource_permission("alert", "create"))]
def generate_autonomous_alert(
    alert_type: str,  # "KPI_FALLEN", "DECISION_VIOLATES_POLICY", "FORECAST_NEED"
    content: Dict[str, Any],  # Alert-specific content
    escalate_to_node_id: str,  # Who should this alert go to
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    System autonomously generates alert/message to human

    This is how the system tells humans they're wrong or asks them to take action

    Alert Types:
    1. KPI_FALLEN: "Your recruitment KPI fell below threshold. Need +2 recruiters or delay timeline"
    2. DECISION_VIOLATES_POLICY: "Your decision violates margin floor constraint. Please override with justification"
    3. FORECAST_NEED: "Forecasting shows we need 10 Rust developers by EOQ. Escalating to VP Engineering"

    Returns:
    - Alert ID for tracking
    - Alert content (subject, body)
    - Response deadline
    - Auto-escalation if no response
    """
    try:
        alert = AutonomousForecastingService.generate_autonomous_alert_to_human(
            db, alert_type, content, escalate_to_node_id
        )

        return {"status": "success", "data": alert}

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Alert generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/summary")
    dependencies=[Depends(require_resource_permission("health", "view"))]
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
