"""API Endpoints for Spartan Phalanx Integration"""
import logging
from typing import Any, Dict, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.services.spartan_orchestration_service import SpartanOrchestrationService
from app.services.finance_service import FinanceService
from app.services.timesheet_bulk_service import TimesheetBulkService
from app.services.job_management_service import JobManagementService
from app.services.demand_management_service import DemandManagementService
from app.services.kpi_service import KPIService

router = APIRouter(prefix="/spartan", tags=["spartan-integration"])

# Finance Endpoints
@router.post(
    "/finance/invoices",
    dependencies=[Depends(require_resource_permission("finance", "create"))]
)
def create_invoice(
    opportunity_id: str,
    amount: float,
    currency: str = "USD",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new invoice"""
    try:
        return FinanceService.create_invoice(
            db=db,
            opportunity_id=opportunity_id,
            amount=amount,
            currency=currency,
            created_by="api"
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Invoice creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/finance/invoices/{invoice_id}/approve",
    dependencies=[Depends(require_resource_permission("finance", "create"))]
)
def approve_invoice(
    invoice_id: str,
    approved_by: str = "finance@example.com",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Approve an invoice"""
    try:
        return FinanceService.approve_invoice(
            db=db,
            invoice_id=invoice_id,
            approved_by=approved_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Invoice approval failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/finance/invoices/bulk-approve",
    dependencies=[Depends(require_resource_permission("finance", "create"))]
)
def bulk_approve_invoices(
    invoice_ids: List[str],
    approved_by: str = "finance@example.com",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Bulk approve multiple invoices"""
    try:
        return FinanceService.bulk_approve_invoices(
            db=db,
            invoice_ids=invoice_ids,
            approved_by=approved_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Bulk approval failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/finance/revenue/recognize",
    dependencies=[Depends(require_resource_permission("finance", "create"))]
)
def recognize_revenue(
    invoice_id: str,
    amount: float = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Recognize revenue from approved invoice"""
    try:
        return FinanceService.recognize_revenue(
            db=db,
            invoice_id=invoice_id,
            amount=amount
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Revenue recognition failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Timesheet Endpoints
@router.get(
    "/timesheets/pending",
    dependencies=[Depends(require_resource_permission("timesheet", "view"))]
)
def get_pending_timesheets(
    manager_id: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get pending timesheets for approval"""
    try:
        timesheets = TimesheetBulkService.get_pending_timesheets(
            db=db,
            manager_id=manager_id,
            limit=limit
        )
        return {"data": timesheets}
    except Exception as e:
        logger.error(f"Failed to get pending timesheets: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/timesheets/bulk-approve",
    dependencies=[Depends(require_resource_permission("timesheet", "create"))]
)
def bulk_approve_timesheets(
    timesheet_ids: List[str],
    approved_by: str = "manager@example.com",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Bulk approve multiple timesheets"""
    try:
        return TimesheetBulkService.bulk_approve_timesheets(
            db=db,
            timesheet_ids=timesheet_ids,
            approved_by=approved_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Bulk timesheet approval failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/timesheets/kpis",
    dependencies=[Depends(require_resource_permission("timesheet", "view"))]
)
def get_timesheet_kpis(
    manager_id: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get timesheet KPIs"""
    try:
        kpis = TimesheetBulkService.get_timesheet_kpis(
            db=db,
            manager_id=manager_id
        )
        return {"data": kpis}
    except Exception as e:
        logger.error(f"Failed to get timesheet KPIs: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Job Management Endpoints
@router.put(
    "/jobs/{job_id}",
    dependencies=[Depends(require_resource_permission("job", "update"))]
)
def update_job(
    job_id: str,
    title: str = None,
    salary_min: float = None,
    salary_max: float = None,
    updated_by: str = "system",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update job details"""
    try:
        updates = {}
        if title: updates["title"] = title
        if salary_min: updates["salary_min"] = salary_min
        if salary_max: updates["salary_max"] = salary_max

        return JobManagementService.update_job_details(
            db=db,
            job_id=job_id,
            updates=updates,
            updated_by=updated_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Job update failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/jobs/{job_id}/close",
    dependencies=[Depends(require_resource_permission("job", "create"))]
)
def close_job(
    job_id: str,
    reason: str = "FILLED",
    closed_by: str = "system",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Close a job"""
    try:
        return JobManagementService.close_job(
            db=db,
            job_id=job_id,
            reason=reason,
            closed_by=closed_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Job closure failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Demand Management Endpoints
@router.post(
    "/demand",
    dependencies=[Depends(require_resource_permission("demand", "create"))]
)
def create_demand(
    resource_type: str,
    quantity: int,
    business_unit_id: str,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create resource demand"""
    try:
        return DemandManagementService.create_demand(
            db=db,
            resource_type=resource_type,
            quantity=quantity,
            start_date=start_date,
            end_date=end_date,
            business_unit_id=business_unit_id
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Demand creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/demand/{demand_id}",
    dependencies=[Depends(require_resource_permission("demand", "update"))]
)
def adjust_demand(
    demand_id: str,
    new_quantity: int,
    adjusted_by: str = "system",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Adjust demand quantity"""
    try:
        return DemandManagementService.adjust_demand_quantity(
            db=db,
            demand_id=demand_id,
            new_quantity=new_quantity,
            adjusted_by=adjusted_by
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Demand adjustment failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# KPI Endpoints
@router.get(
    "/kpis/{phalanx}",
    dependencies=[Depends(require_resource_permission("kpi", "view"))]
)
def get_kpi(
    phalanx: str,
    period: str = "weekly",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get phalanx health score and KPIs"""
    try:
        health = KPIService.get_phalanx_health_score(db, phalanx, period)
        return {"data": health}
    except Exception as e:
        logger.error(f"Failed to get KPI: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Orchestration Endpoints
@router.post(
    "/operations/queue",
    dependencies=[Depends(require_resource_permission("operation", "create"))]
)
def queue_operation(
    phalanx: str,  # "recruitment", "resource_management", "finance"
    operation: str,
    payload: Dict[str, Any],
    priority: str = "NORMAL",
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Queue an operation through Spartan orchestration"""
    try:
        if phalanx == "recruitment":
            return SpartanOrchestrationService.queue_recruitment_operation(
                db=db,
                operation=operation,
                payload=payload,
                priority=priority
            )
        elif phalanx == "resource_management":
            return SpartanOrchestrationService.queue_resource_operation(
                db=db,
                operation=operation,
                payload=payload,
                priority=priority
            )
        elif phalanx == "finance":
            return SpartanOrchestrationService.queue_finance_operation(
                db=db,
                operation=operation,
                payload=payload,
                priority=priority
            )
        else:
            raise ValueError(f"Unknown phalanx: {phalanx}")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Operation queueing failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/formation/status",
    dependencies=[Depends(require_resource_permission("formation", "view"))]
)
def get_formation_status(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get overall Spartan formation status"""
    try:
        status = SpartanOrchestrationService.get_spartan_formation_status(db)
        return {"data": status}
    except Exception as e:
        logger.error(f"Failed to get formation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/phalanx/{phalanx}/integrity",
    dependencies=[Depends(require_resource_permission("phalanx", "view"))]
)
def check_integrity(
    phalanx: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Check phalanx formation integrity"""
    try:
        integrity = SpartanOrchestrationService.check_phalanx_integrity(db, phalanx)
        return {"data": integrity}
    except Exception as e:
        logger.error(f"Failed to check integrity: {e}")
        raise HTTPException(status_code=400, detail=str(e))
