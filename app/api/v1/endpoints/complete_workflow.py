"""
REST Endpoints for Complete Candidate-to-Invoice Workflow
Integrates all 15+ story endpoints into unified API.
"""
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

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Initialize services
interview_service = InterviewDecisionService()
offer_service = OfferManagementService()
employee_service = EmployeeConversionService()
timesheet_service = TimesheetCompleteService()
invoice_service = InvoiceCompleteService()
revenue_service = RevenueRecognitionService()
allocation_service = ProjectAllocationService()
scoring_service = CandidateScoringService()
hm_validation_service = HiringManagerValidationService()
core_pull_service = CorePullService()

# ============ INTERVIEW DECISIONS ============
@router.get("/interviews/{interview_id}/status")
def get_interview_status(interview_id: int, db: Session = Depends(get_db)):
    """Get complete interview status with all feedback."""
    return interview_service.get_interview_status(db, interview_id, tenant_id=1)

@router.post("/interviews/{interview_id}/decide")
def calculate_interview_decision(interview_id: int, db: Session = Depends(get_db)):
    """Calculate panel decision from feedback."""
    return interview_service.calculate_panel_decision(db, interview_id, tenant_id=1)

# ============ OFFERS ============
@router.post("/offers")
def create_offer(candidate_id: str, job_id: str, salary: int, db: Session = Depends(get_db)):
    """Create new offer."""
    return offer_service.create_offer(db, candidate_id, job_id, 1, salary, "Position", datetime.utcnow())

@router.post("/offers/{offer_id}/approve")
def approve_offer(offer_id: str, approved_by: str, db: Session = Depends(get_db)):
    """Approve offer for sending."""
    return offer_service.approve_offer(db, offer_id, 1, approved_by)

@router.post("/offers/{offer_id}/send")
def send_offer(offer_id: str, candidate_email: str, db: Session = Depends(get_db)):
    """Send offer to candidate."""
    return offer_service.send_offer_to_candidate(db, offer_id, 1, candidate_email)

@router.post("/offers/{offer_id}/accept")
def accept_offer(offer_id: str, candidate_id: str, db: Session = Depends(get_db)):
    """Accept offer."""
    return offer_service.accept_offer(db, offer_id, 1, candidate_id)

# ============ EMPLOYEE CONVERSION ============
@router.post("/employees/convert")
def convert_candidate(candidate_id: str, name: str, email: str, bu_id: int, db: Session = Depends(get_db)):
    """Convert candidate to employee."""
    return employee_service.convert_candidate_to_employee(db, candidate_id, 1, name, email, bu_id, "Position", datetime.utcnow())

# ============ PROJECT ALLOCATION ============
@router.post("/allocations")
def allocate_to_project(employee_id: str, project_id: str, db: Session = Depends(get_db)):
    """Allocate employee to project."""
    return allocation_service.allocate_employee_to_project(db, employee_id, project_id, 1, datetime.utcnow())

# ============ TIMESHEETS ============
@router.post("/timesheets")
def create_timesheet(employee_id: str, allocation_id: str, db: Session = Depends(get_db)):
    """Create timesheet."""
    return timesheet_service.create_timesheet(db, employee_id, allocation_id, 1, datetime.utcnow())

@router.post("/timesheets/{timesheet_id}/submit")
def submit_timesheet(timesheet_id: str, db: Session = Depends(get_db)):
    """Submit timesheet."""
    return timesheet_service.submit_timesheet(db, timesheet_id, 1)

@router.post("/timesheets/{timesheet_id}/approve")
def approve_timesheet(timesheet_id: str, approver_id: str, db: Session = Depends(get_db)):
    """Approve timesheet."""
    return timesheet_service.approve_timesheet(db, timesheet_id, 1, approver_id)

# ============ INVOICES ============
@router.post("/invoices/generate")
def generate_invoice(client_id: str, project_id: str, db: Session = Depends(get_db)):
    """Generate invoice from timesheets."""
    return invoice_service.generate_invoice_from_timesheets(db, client_id, project_id, 1, datetime.utcnow(), datetime.utcnow(), 10000)

@router.post("/invoices/{invoice_id}/send")
def send_invoice(invoice_id: str, client_email: str, db: Session = Depends(get_db)):
    """Send invoice to client."""
    return invoice_service.send_invoice_to_client(db, invoice_id, 1, client_email)

@router.post("/invoices/{invoice_id}/payment")
def record_payment(invoice_id: str, amount: int, db: Session = Depends(get_db)):
    """Record payment received."""
    return invoice_service.record_payment(db, invoice_id, 1, amount, datetime.utcnow(), "ACH")

# ============ REVENUE ============
@router.post("/revenue/recognize")
def recognize_revenue(invoice_id: str, db: Session = Depends(get_db)):
    """Recognize revenue from invoice."""
    return revenue_service.recognize_revenue_from_invoice(db, invoice_id, 1, "MONTHLY")

@router.get("/revenue/arr/{client_id}")
def get_arr(client_id: str, db: Session = Depends(get_db)):
    """Get annual recurring revenue."""
    return revenue_service.calculate_asr(db, client_id, 1, datetime.utcnow(), datetime.utcnow())

# ============ CANDIDATE SCORING ============
@router.post("/candidates/{candidate_id}/score")
def score_candidate(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    """Score candidate against job."""
    return scoring_service.calculate_fit_score(db, candidate_id, job_id, 1)

@router.get("/jobs/{job_id}/candidates/ranked")
def rank_candidates(job_id: str, db: Session = Depends(get_db)):
    """Rank all candidates for job."""
    return scoring_service.rank_candidates(db, job_id, 1)

# ============ HIRING MANAGER VALIDATION ============
@router.post("/validation/send")
def send_validation(job_id: str, candidate_id: str, hm_email: str, db: Session = Depends(get_db)):
    """Send validation to hiring manager."""
    return hm_validation_service.send_validation_to_hm(db, job_id, candidate_id, hm_email, 1)

@router.post("/validation/{validation_id}/respond")
def record_validation_response(validation_id: str, decision: str, db: Session = Depends(get_db)):
    """Record HM validation response."""
    return hm_validation_service.record_hm_response(db, validation_id, 1, {}, decision)

# ============ CORE-PULL ============
@router.post("/allocations/{allocation_id}/core-pull")
def apply_core_pull(allocation_id: str, db: Session = Depends(get_db)):
    """Apply core-pull rules."""
    return core_pull_service.apply_core_pull_rule(db, allocation_id, 1)
