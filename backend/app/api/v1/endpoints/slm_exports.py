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
from app.services.slm_export_service import SLMExportService
from app.core.permissions import require_resource_permission, Permissions

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/slm/export",
    tags=["SLM Export"],
    dependencies=[Depends(get_db)]
)


@router.get(
    "/performance-scores",
    dependencies=[Depends(require_resource_permission(*Permissions.EMPLOYEES_VIEW))]
)
def get_performance_scores(
    date: str = Query(None, description="YYYY-MM-DD format. Defaults to today."),
    db: Session = Depends(get_db)
):
    """
    Export employee performance scores for P&L calculations.

    **Used by:**
    - Bonus Agent: determines bonus eligibility
    - Revenue Agent: calculates billing rates
    - Sourcing Agent: finds performance benchmarks

    **Latency SLA:** <5 minutes
    **Frequency:** Daily 9 PM UTC

    **Response Example:**
    ```json
    {
      "export_date": "2026-09-18",
      "employees": [
        {
          "id": "emp_123",
          "name": "Alice",
          "performance_score": 92,
          "skills": [
            {"name": "Python", "level": "Expert", "years": 5}
          ]
        }
      ]
    }
    ```
    """
    try:
        result = SLMExportService.export_performance_scores(db, date)
        return result
    except Exception as e:
        logger.error(f"Error fetching performance scores: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get(
    "/available-employees",
    dependencies=[Depends(require_resource_permission(*Permissions.EMPLOYEES_VIEW))]
)
def get_available_employees(db: Session = Depends(get_db)):
    """
    Export employees available for allocation (real-time).

    **Used by:**
    - Allocation Agent: find available people
    - Workspace Agent: allocate to projects
    - Bench Cost Agent: track bench employees

    **Latency SLA:** <5 seconds (real-time event-driven)
    **Frequency:** Event-driven (when employee status changes)

    **Response Example:**
    ```json
    {
      "timestamp": "2026-09-18T14:30:00Z",
      "available_employees": [
        {
          "employee_id": "emp_001",
          "name": "Alice",
          "status": "bench",
          "bench_duration_days": 8,
          "skills": ["Python", "AWS"],
          "performance_score": 92,
          "billable_rate": 180
        }
      ]
    }
    ```
    """
    try:
        result = SLMExportService.export_available_employees(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching available employees: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get(
    "/utilization-snapshot",
    dependencies=[Depends(require_resource_permission(*Permissions.REPORTS_VIEW))]
)
def get_utilization_snapshot(db: Session = Depends(get_db)):
    """
    Export company-wide utilization metrics.

    **Used by:**
    - Utilization Agent: track vs 90% target
    - Cost Agent: bench cost calculations
    - FLASH: allocation prioritization
    - P&L Dashboard: real-time metrics

    **Latency SLA:** <5 minutes
    **Frequency:** Daily 8 AM UTC

    **Response Example:**
    ```json
    {
      "snapshot_date": "2026-09-18",
      "company_utilization_pct": 87.5,
      "target_utilization_pct": 90,
      "variance": -2.5,
      "employees_bench": 3,
      "bench_cost_per_day": 1200
    }
    ```
    """
    try:
        result = SLMExportService.export_utilization_snapshot(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching utilization snapshot: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get(
    "/project-profitability",
    dependencies=[Depends(require_resource_permission(*Permissions.REPORTS_VIEW))]
)
def get_project_profitability(db: Session = Depends(get_db)):
    """
    Export project-level profitability (cost + revenue).

    **Used by:**
    - Margin Agent: rank projects by margin %
    - Allocation Agent: assign people to highest-margin projects
    - FLASH: staffing prioritization

    **Latency SLA:** <5 minutes
    **Frequency:** Daily 8 AM UTC

    **Response Example:**
    ```json
    {
      "projects": [
        {
          "project_id": "proj_001",
          "project_name": "Client A",
          "margin_pct": 40,
          "priority_for_staffing": "high"
        }
      ]
    }
    ```
    """
    try:
        result = SLMExportService.export_project_profitability(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching project profitability: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get(
    "/hiring-benchmarks",
    dependencies=[Depends(require_resource_permission(*Permissions.RECRUITMENT_VIEW))]
)
def get_hiring_benchmarks(db: Session = Depends(get_db)):
    """
    Export performance benchmarks for sourcing/hiring.

    **Used by:**
    - Sourcing Agent: find candidates matching top performers
    - Screening Agent: quality thresholds (>80 score)
    - Interview Agent: evaluation standards

    **Latency SLA:** <5 minutes
    **Frequency:** Weekly Monday 9 AM UTC

    **Response Example:**
    ```json
    {
      "by_skill": {
        "Python": {
          "average_performance_score": 85,
          "quality_benchmark": 80
        }
      },
      "hiring_quality_target": 75
    }
    ```
    """
    try:
        result = SLMExportService.export_hiring_pipeline_benchmark(db)
        return result
    except Exception as e:
        logger.error(f"Error fetching hiring benchmarks: {e}", exc_info=True)
        return {"error": str(e), "status": 500}


@router.get(
    "/health",
    dependencies=[Depends(require_resource_permission(*Permissions.SYSTEM_VIEW))]
)
def slm_export_health(db: Session = Depends(get_db)):
    """
    Health check for SLM export service.

    Used by: Monitoring dashboard, FLASH orchestrator, P&L agents
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "SLM Export",
        "last_export": datetime.utcnow().isoformat() + "Z"
    }
