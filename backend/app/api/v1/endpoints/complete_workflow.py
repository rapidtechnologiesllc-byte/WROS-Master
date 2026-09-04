"""
REST Endpoints for Complete Candidate-to-Invoice Workflow
Integrates all 15+ story endpoints into unified API.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.services.interview_decision_service import InterviewDecisionService
from app.services.offer_management_service import OfferManagementService
from app.services.employee_conversion_service import EmployeeConversionService
from app.services.timesheet_complete_service import TimesheetCompleteService
from app.services.invoice_complete_service import InvoiceCompleteService
from app.services.revenue_recognition_service import RevenueRecognitionService
from app.services.project_allocation_service import ProjectAllocationService
from app.services.candidate_scoring_service import CandidateScoringService
from app.services.hiring_manager_validation_service import HiringManagerValidationService
from app.services.core_pull_service import CorePullService
from app.core.logging import logger

router = APIRouter(prefix="/workflow", tags=["workflow"])
logger = logging.getLogger(__name__)

def _get_services():
    """Factory function to create service instances."""
    return {
        'interview': InterviewDecisionService(),
        'offer': OfferManagementService(),
        'employee': EmployeeConversionService(),
        'timesheet': TimesheetCompleteService(),
        'invoice': InvoiceCompleteService(),
        'revenue': RevenueRecognitionService(),
        'allocation': ProjectAllocationService(),
        'scoring': CandidateScoringService(),
        'hm_validation': HiringManagerValidationService(),
        'core_pull': CorePullService(),
    }

# ============ INTERVIEW DECISIONS ============
@router.get(
    "/interviews/{interview_id}/status",
    dependencies=[Depends(require_resource_permission("interview", "view"))]
)
def get_interview_status(interview_id: int, db: Session = Depends(get_db)):
    """Get complete interview status with all feedback."""
    if not interview_id:
        raise HTTPException(status_code=400, detail="interview_id is required")

    try:
        services = _get_services()
        result = services['interview'].get_interview_status(db, interview_id, tenant_id=1)
        if not result:
            raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get interview status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get interview status: {str(e)}")

@router.post(
    "/interviews/{interview_id}/decide",
    dependencies=[Depends(require_resource_permission("interview", "create"))]
)
def calculate_interview_decision(interview_id: int, db: Session = Depends(get_db)):
    """Calculate panel decision from feedback."""
    if not interview_id:
        raise HTTPException(status_code=400, detail="interview_id is required")

    try:
        services = _get_services()
        result = services['interview'].calculate_panel_decision(db, interview_id, tenant_id=1)
        if not result:
            raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate interview decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate interview decision: {str(e)}")

# ============ OFFERS ============
@router.post(
    "/offers",
    dependencies=[Depends(require_resource_permission("offer", "create"))]
)
def create_offer(candidate_id: str, job_id: str, salary: int, db: Session = Depends(get_db)):
    """Create new offer."""
    if not candidate_id or not job_id or not salary:
        raise HTTPException(status_code=400, detail="candidate_id, job_id, and salary are required")
    if salary <= 0:
        raise HTTPException(status_code=400, detail="salary must be greater than 0")

    try:
        services = _get_services()
        result = services['offer'].create_offer(db, candidate_id, job_id, 1, salary, "Position", datetime.utcnow())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create offer")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create offer: {str(e)}")

@router.post(
    "/offers/{offer_id}/approve",
    dependencies=[Depends(require_resource_permission("offer", "create"))]
)
def approve_offer(offer_id: str, approved_by: str, db: Session = Depends(get_db)):
    """Approve offer for sending."""
    if not offer_id or not approved_by:
        raise HTTPException(status_code=400, detail="offer_id and approved_by are required")

    try:
        services = _get_services()
        result = services['offer'].approve_offer(db, offer_id, 1, approved_by)
        if not result:
            raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to approve offer: {str(e)}")

@router.post(
    "/offers/{offer_id}/send",
    dependencies=[Depends(require_resource_permission("offer", "create"))]
)
def send_offer(offer_id: str, candidate_email: str, db: Session = Depends(get_db)):
    """Send offer to candidate."""
    if not offer_id or not candidate_email:
        raise HTTPException(status_code=400, detail="offer_id and candidate_email are required")
    if '@' not in candidate_email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    try:
        services = _get_services()
        result = services['offer'].send_offer_to_candidate(db, offer_id, 1, candidate_email)
        if not result:
            raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send offer: {str(e)}")

@router.post(
    "/offers/{offer_id}/accept",
    dependencies=[Depends(require_resource_permission("offer", "create"))]
)
def accept_offer(offer_id: str, candidate_id: str, db: Session = Depends(get_db)):
    """Accept offer."""
    if not offer_id or not candidate_id:
        raise HTTPException(status_code=400, detail="offer_id and candidate_id are required")

    try:
        services = _get_services()
        result = services['offer'].accept_offer(db, offer_id, 1, candidate_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Offer {offer_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to accept offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to accept offer: {str(e)}")

# ============ EMPLOYEE CONVERSION ============
@router.post(
    "/employees/convert",
    dependencies=[Depends(require_resource_permission("employee", "create"))]
)
def convert_candidate(candidate_id: str, name: str, email: str, bu_id: int, db: Session = Depends(get_db)):
    """Convert candidate to employee."""
    if not candidate_id or not name or not email or not bu_id:
        raise HTTPException(status_code=400, detail="candidate_id, name, email, and bu_id are required")
    if '@' not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if bu_id <= 0:
        raise HTTPException(status_code=400, detail="bu_id must be positive")

    try:
        services = _get_services()
        result = services['employee'].convert_candidate_to_employee(db, candidate_id, 1, name, email, bu_id, "Position", datetime.utcnow())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to convert candidate to employee")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to convert candidate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to convert candidate: {str(e)}")

# ============ PROJECT ALLOCATION ============
@router.post(
    "/allocations",
    dependencies=[Depends(require_resource_permission("allocation", "create"))]
)
def allocate_to_project(employee_id: str, project_id: str, db: Session = Depends(get_db)):
    """Allocate employee to project."""
    if not employee_id or not project_id:
        raise HTTPException(status_code=400, detail="employee_id and project_id are required")

    try:
        services = _get_services()
        result = services['allocation'].allocate_employee_to_project(db, employee_id, project_id, 1, datetime.utcnow())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to allocate employee to project")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to allocate employee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to allocate employee: {str(e)}")

# ============ TIMESHEETS ============
@router.post(
    "/timesheets",
    dependencies=[Depends(require_resource_permission("timesheet", "create"))]
)
def create_timesheet(employee_id: str, allocation_id: str, db: Session = Depends(get_db)):
    """Create timesheet."""
    if not employee_id or not allocation_id:
        raise HTTPException(status_code=400, detail="employee_id and allocation_id are required")

    try:
        services = _get_services()
        result = services['timesheet'].create_timesheet(db, employee_id, allocation_id, 1, datetime.utcnow())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create timesheet")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create timesheet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create timesheet: {str(e)}")

@router.post(
    "/timesheets/{timesheet_id}/submit",
    dependencies=[Depends(require_resource_permission("timesheet", "create"))]
)
def submit_timesheet(timesheet_id: str, db: Session = Depends(get_db)):
    """Submit timesheet."""
    if not timesheet_id:
        raise HTTPException(status_code=400, detail="timesheet_id is required")

    try:
        services = _get_services()
        result = services['timesheet'].submit_timesheet(db, timesheet_id, 1)
        if not result:
            raise HTTPException(status_code=404, detail=f"Timesheet {timesheet_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit timesheet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit timesheet: {str(e)}")

@router.post(
    "/timesheets/{timesheet_id}/approve",
    dependencies=[Depends(require_resource_permission("timesheet", "create"))]
)
def approve_timesheet(timesheet_id: str, approver_id: str, db: Session = Depends(get_db)):
    """Approve timesheet."""
    if not timesheet_id or not approver_id:
        raise HTTPException(status_code=400, detail="timesheet_id and approver_id are required")

    try:
        services = _get_services()
        result = services['timesheet'].approve_timesheet(db, timesheet_id, 1, approver_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Timesheet {timesheet_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve timesheet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to approve timesheet: {str(e)}")

# ============ INVOICES ============
@router.post(
    "/invoices/generate",
    dependencies=[Depends(require_resource_permission("invoice", "create"))]
)
def generate_invoice(client_id: str, project_id: str, db: Session = Depends(get_db)):
    """Generate invoice from timesheets."""
    if not client_id or not project_id:
        raise HTTPException(status_code=400, detail="client_id and project_id are required")

    try:
        services = _get_services()
        result = services['invoice'].generate_invoice_from_timesheets(db, client_id, project_id, 1, datetime.utcnow(), datetime.utcnow(), 10000)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to generate invoice")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

@router.post(
    "/invoices/{invoice_id}/send",
    dependencies=[Depends(require_resource_permission("invoice", "create"))]
)
def send_invoice(invoice_id: str, client_email: str, db: Session = Depends(get_db)):
    """Send invoice to client."""
    if not invoice_id or not client_email:
        raise HTTPException(status_code=400, detail="invoice_id and client_email are required")
    if '@' not in client_email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    try:
        services = _get_services()
        result = services['invoice'].send_invoice_to_client(db, invoice_id, 1, client_email)
        if not result:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send invoice: {str(e)}")

@router.post(
    "/invoices/{invoice_id}/payment",
    dependencies=[Depends(require_resource_permission("invoice", "create"))]
)
def record_payment(invoice_id: str, amount: int, db: Session = Depends(get_db)):
    """Record payment received."""
    if not invoice_id or not amount:
        raise HTTPException(status_code=400, detail="invoice_id and amount are required")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    try:
        services = _get_services()
        result = services['invoice'].record_payment(db, invoice_id, 1, amount, datetime.utcnow(), "ACH")
        if not result:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record payment: {str(e)}")

# ============ REVENUE ============
@router.post(
    "/revenue/recognize",
    dependencies=[Depends(require_resource_permission("revenue", "create"))]
)
def recognize_revenue(invoice_id: str, db: Session = Depends(get_db)):
    """Recognize revenue from invoice."""
    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoice_id is required")

    try:
        services = _get_services()
        result = services['revenue'].recognize_revenue_from_invoice(db, invoice_id, 1, "MONTHLY")
        if not result:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recognize revenue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recognize revenue: {str(e)}")

@router.get(
    "/revenue/arr/{client_id}",
    dependencies=[Depends(require_resource_permission("revenue", "view"))]
)
def get_arr(client_id: str, db: Session = Depends(get_db)):
    """Get annual recurring revenue."""
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    try:
        services = _get_services()
        result = services['revenue'].calculate_asr(db, client_id, 1, datetime.utcnow(), datetime.utcnow())
        if result is None:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        return {"arr": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate ARR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate ARR: {str(e)}")

# ============ CANDIDATE SCORING ============
@router.post(
    "/candidates/{candidate_id}/score",
    dependencies=[Depends(require_resource_permission("candidate", "create"))]
)
def score_candidate(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    """Score candidate against job."""
    if not candidate_id or not job_id:
        raise HTTPException(status_code=400, detail="candidate_id and job_id are required")

    try:
        services = _get_services()
        result = services['scoring'].calculate_fit_score(db, candidate_id, job_id, 1)
        if result is None:
            raise HTTPException(status_code=404, detail="Candidate or job not found")
        return {"score": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to score candidate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to score candidate: {str(e)}")

@router.get(
    "/jobs/{job_id}/candidates/ranked",
    dependencies=[Depends(require_resource_permission("job", "view"))]
)
def rank_candidates(job_id: str, db: Session = Depends(get_db)):
    """Rank all candidates for job."""
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    try:
        services = _get_services()
        result = services['scoring'].rank_candidates(db, job_id, 1)
        if not result:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or no candidates")
        return {"candidates": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rank candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rank candidates: {str(e)}")

# ============ HIRING MANAGER VALIDATION ============
@router.post(
    "/validation/send",
    dependencies=[Depends(require_resource_permission("validation", "create"))]
)
def send_validation(job_id: str, candidate_id: str, hm_email: str, db: Session = Depends(get_db)):
    """Send validation to hiring manager."""
    if not job_id or not candidate_id or not hm_email:
        raise HTTPException(status_code=400, detail="job_id, candidate_id, and hm_email are required")
    if '@' not in hm_email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    try:
        services = _get_services()
        result = services['hm_validation'].send_validation_to_hm(db, job_id, candidate_id, hm_email, 1)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to send validation")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send validation: {str(e)}")

@router.post(
    "/validation/{validation_id}/respond",
    dependencies=[Depends(require_resource_permission("validation", "create"))]
)
def record_validation_response(validation_id: str, decision: str, db: Session = Depends(get_db)):
    """Record HM validation response."""
    if not validation_id or not decision:
        raise HTTPException(status_code=400, detail="validation_id and decision are required")
    if decision not in ["approved", "rejected", "maybe"]:
        raise HTTPException(status_code=400, detail="decision must be 'approved', 'rejected', or 'maybe'")

    try:
        services = _get_services()
        result = services['hm_validation'].record_hm_response(db, validation_id, 1, {}, decision)
        if not result:
            raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record validation response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record validation response: {str(e)}")

# ============ CORE-PULL ============
@router.post(
    "/allocations/{allocation_id}/core-pull",
    dependencies=[Depends(require_resource_permission("allocation", "create"))]
)
def apply_core_pull(allocation_id: str, db: Session = Depends(get_db)):
    """Apply core-pull rules."""
    if not allocation_id:
        raise HTTPException(status_code=400, detail="allocation_id is required")

    try:
        services = _get_services()
        result = services['core_pull'].apply_core_pull_rule(db, allocation_id, 1)
        if not result:
            raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply core-pull: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply core-pull: {str(e)}")
