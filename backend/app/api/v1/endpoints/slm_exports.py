"""
SLM Export API Endpoints

These endpoints are queried by:
- P&L agents (Revenue, Cost, Margin, Budget, Bonus)
- Recruitment agents (Sourcing, Screening, Interview)
- Workforce agents (Allocation, Utilization, Skill Gap)
- FLASH orchestrator

Latency SLA: <5 min (loose coupling, daily batch OK)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, date as date_type
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.slm_export_service import SLMExportService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/slm/export",
    tags=["SLM Export"],
    dependencies=[Depends(get_db)]
)


@router.get("/performance-scores")
def get_performance_scores(
    date: str = Query(None, description="YYYY-MM-DD format. Defaults to today."),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export employee performance scores for P&L calculations."""
    try:
        result = SLMExportService.export_performance_scores(db, date)
        return result
    except Exception as e:
        logger.error(f"Error fetching performance scores: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get("/available-employees")
def get_available_employees(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export employees available for allocation (real-time)."""
    try:
        result = SLMExportService.export_available_employees(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching available employees: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get("/utilization-snapshot")
def get_utilization_snapshot(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export company-wide utilization metrics."""
    try:
        result = SLMExportService.export_utilization_snapshot(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching utilization snapshot: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get("/project-profitability")
def get_project_profitability(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export project-level profitability (cost + revenue)."""
    try:
        result = SLMExportService.export_project_profitability(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching project profitability: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get("/hiring-benchmarks")
def get_hiring_benchmarks(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export performance benchmarks for sourcing/hiring."""
    try:
        result = SLMExportService.export_hiring_pipeline_benchmark(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching hiring benchmarks: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get("/health")
def slm_export_health(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Health check for SLM export service."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "SLM Export",
        "last_export": datetime.utcnow().isoformat() + "Z"
    }
