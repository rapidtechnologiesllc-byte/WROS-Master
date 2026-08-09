"""Spartan Phalanx Formation API - Shield wall monitoring and integrity tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.services.agent_shield_service import PhalanxFormationService
from app.core.dependencies import get_current_user_or_none

router = APIRouter(prefix="/phalanx", tags=["phalanx"])


@router.get("/formations")
def get_phalanx_formations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """
    Get all phalanx formations and their status.

    Recruitment → Resource → Finance phalanxes
    Each showing formation strength, agent shields, and critical alerts.
    """
    try:
        phalanxes = []
        for phalanx_name in PhalanxFormationService.PHALANXES.keys():
            status = PhalanxFormationService.get_phalanx_status(db, phalanx_name)
            phalanxes.append(status)

        return {
            "status": "retrieved",
            "total_phalanxes": len(phalanxes),
            "phalanxes": phalanxes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formations/{phalanx_name}")
def get_phalanx_status(
    phalanx_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """
    Get detailed status of a specific phalanx formation.

    Shows:
    - Position-by-position shield strength
    - Agent relationships (left neighbor, right neighbor)
    - Formation integrity percentage
    - Recent alerts and vulnerabilities
    - Breach risk score
    """
    status = PhalanxFormationService.get_phalanx_status(db, phalanx_name)

    if status.get("status") == "error":
        raise HTTPException(status_code=404, detail=status.get("message"))

    return status


@router.post("/formations/{phalanx_name}/initialize")
def initialize_phalanx(
    phalanx_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """Initialize a phalanx formation with agent positions."""

    # Check if user is admin
    if not current_user or not getattr(current_user, "role", None) == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get agents for this phalanx
    phalanx_config = PhalanxFormationService.PHALANXES.get(phalanx_name)
    if not phalanx_config:
        raise HTTPException(status_code=404, detail=f"Phalanx '{phalanx_name}' not found")

    # Initialize
    success = PhalanxFormationService.initialize_phalanx_formation(
        db, phalanx_name, phalanx_config["agents"]
    )

    if success:
        return {
            "status": "initialized",
            "phalanx_name": phalanx_name,
            "agents": phalanx_config["agents"],
            "formation_sla": phalanx_config["formation_sla"],
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize phalanx")


@router.put("/agent-shield/{phalanx_name}/{agent_name}")
def update_agent_shield(
    phalanx_name: str,
    agent_name: str,
    success_rate: float = Query(..., ge=0, le=100),
    latency_ms: int = Query(..., ge=0),
    quality_score: float = Query(..., ge=0, le=100),
    confidence: float = Query(..., ge=0, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """
    Update an agent's shield metrics and check formation integrity.

    This is called by agents reporting their performance:
    - success_rate: % of executions that succeeded (0-100)
    - latency_ms: Average response time (milliseconds)
    - quality_score: Output quality assessment (0-100)
    - confidence: Confidence in the result (0-100)

    The API calculates shield strength and alerts if formation is weakening.
    """

    result = PhalanxFormationService.update_shield_strength(
        db,
        phalanx_name,
        agent_name,
        success_rate,
        latency_ms,
        quality_score,
        confidence,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.get("/formation-integrity/{phalanx_name}")
def get_formation_integrity(
    phalanx_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """
    Get phalanx formation integrity analysis.

    Shows:
    - Overall formation strength (0-100%)
    - Individual shield distribution
    - Weakest link (bottleneck position)
    - Breach risk score
    - Cascading failure scenarios
    - Recommendations for reinforcement
    """

    integrity = PhalanxFormationService.calculate_formation_integrity(db, phalanx_name)

    if integrity.get("status") == "error":
        raise HTTPException(status_code=404, detail=integrity.get("message"))

    return integrity


@router.get("/dashboard/phalanx-wall")
def get_phalanx_wall_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_or_none),
):
    """
    Get the complete Phalanx Wall dashboard showing all formations.

    Visualizes:
    - Three phalanxes (Recruitment, Resource, Finance)
    - Each agent's shield position and strength
    - Formation integrity for each phalanx
    - Critical alerts across all formations
    - Overall WROS health score

    This is the high-level view that shows:
    "Are all Spartans holding the line?"
    """

    try:
        phalanxes_data = []
        critical_alerts = []

        for phalanx_name in PhalanxFormationService.PHALANXES.keys():
            phalanx_status = PhalanxFormationService.get_phalanx_status(db, phalanx_name)
            integrity = PhalanxFormationService.calculate_formation_integrity(db, phalanx_name)

            phalanx_info = {
                "phalanx_name": phalanx_name,
                "formation_strength": phalanx_status.get("formation_strength", 0),
                "overall_status": phalanx_status.get("overall_status", "UNKNOWN"),
                "agents": phalanx_status.get("agents", []),
                "integrity": integrity,
                "alerts": phalanx_status.get("alerts", 0),
            }

            phalanxes_data.append(phalanx_info)

            # Add critical alerts to dashboard
            if phalanx_status.get("alerts", 0) > 0:
                critical_alerts.append({
                    "phalanx": phalanx_name,
                    "alert_count": phalanx_status.get("alerts", 0),
                    "alert_types": phalanx_status.get("recent_alert_types", []),
                })

        # Calculate overall WROS health
        overall_strength = sum(p["formation_strength"] for p in phalanxes_data) / len(phalanxes_data)
        overall_status = "OPERATIONAL" if overall_strength >= 85 else "ALERT"

        return {
            "status": "retrieved",
            "dashboard": "Phalanx Wall",
            "timestamp": "",
            "overall_wros_health": {
                "strength": overall_strength,
                "status": overall_status,
                "message": "All Spartans holding the line!" if overall_strength >= 90 else "Formation weakening - check individual phalanxes",
            },
            "phalanxes": phalanxes_data,
            "critical_alerts": critical_alerts,
            "philosophy": "Each agent protects the one to their left. We stand together or fall apart.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
