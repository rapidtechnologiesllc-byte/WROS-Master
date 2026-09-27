"""Architect findings and analysis endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import logging

from app.core.dependencies import require_resource_permission
from app.services.autonomous_architect import (
    get_autonomous_architect,
    FindingsGenerator,
)

router = APIRouter(
    prefix="/architect",
    tags=["architect"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)

logger = logging.getLogger(__name__)


@router.get("/findings")
async def get_latest_findings() -> Dict[str, Any]:
    """Get latest architect findings"""
    try:
        architect = get_autonomous_architect(None)  # Uses existing instance
        findings = await architect.get_latest_findings()

        return {
            "cycle": architect.cycle_count,
            "total_findings": len(findings),
            "findings": [f.to_dict() for f in findings][:50],  # Limit to first 50
        }
    except Exception as e:
        logger.error(f"Error getting findings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_architect_report() -> Dict[str, Any]:
    """Get human-readable architect report"""
    try:
        architect = get_autonomous_architect(None)
        findings = await architect.get_latest_findings()
        report = FindingsGenerator.generate_report(findings)

        return {
            "cycle": architect.cycle_count,
            "report": report,
        }
    except Exception as e:
        logger.error(f"Error getting report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spec")
async def get_next_cycle_spec() -> Dict[str, Any]:
    """Get spec for next SDLC cycle"""
    try:
        architect = get_autonomous_architect(None)
        findings = await architect.get_latest_findings()
        spec = FindingsGenerator.generate_sdlc_spec(findings)

        return spec
    except Exception as e:
        logger.error(f"Error getting spec: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_architect_status() -> Dict[str, Any]:
    """Get architect service status"""
    try:
        architect = get_autonomous_architect(None)
        findings = await architect.get_latest_findings()

        return {
            "running": architect.running,
            "cycle": architect.cycle_count,
            "last_findings_count": len(findings),
            "service": "autonomous_architect"
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
