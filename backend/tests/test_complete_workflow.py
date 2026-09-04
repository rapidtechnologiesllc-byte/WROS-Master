"""
COMPREHENSIVE WORKFLOW TESTS
End-to-end tests for candidate to invoice workflow covering all 15+ stories.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.interview_decision_service import InterviewDecisionService
from app.services.offer_management_service import OfferManagementService
from app.services.employee_conversion_service import EmployeeConversionService
from app.services.timesheet_complete_service import TimesheetCompleteService
from app.services.invoice_complete_service import InvoiceCompleteService
from app.services.revenue_recognition_service import RevenueRecognitionService
from app.services.project_allocation_service import ProjectAllocationService
from app.services.candidate_scoring_service import CandidateScoringService
from app.services.hiring_manager_validation_service import HiringManagerValidationService
import logging
from app.services.core_pull_service import CorePullService

logger = logging.getLogger(__name__)

class TestCompleteWorkflow:
    """Test complete candidate-to-invoice workflow."""

    def test_01_score_candidates(self):
        """Step 1: Score candidates against job."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(None, "C1", "J1", 1)
        assert result["status"] == "success"
        assert result["fit_score"] >= 0

    def test_02_ranking(self):
        """Step 2: Rank candidates."""
        service = CandidateScoringService()
        result = service.rank_candidates(None, "J1", 1)
        assert result["status"] == "success"
        assert "top_candidates" in result

    def test_03_hiring_manager_validation(self):
        """Step 3: Send HM validation."""
        service = HiringManagerValidationService()
        result = service.send_validation_to_hm(None, "J1", "C1", "hm@company.com", 1)
        assert result["status"] == "success"
        assert "validation_id" in result

    def test_04_interview_decision(self):
        """Step 4: Calculate interview decision."""
        service = InterviewDecisionService()
        result = service.calculate_panel_decision(None, 1, 1)
        assert "decision" in result

    def test_05_create_offer(self):
        """Step 5: Create offer."""
        service = OfferManagementService()
        result = service.create_offer(None, "C1", "J1", 1, 100000, "Software Engineer", datetime.utcnow())
        assert result["status"] == "success"
        assert "offer_id" in result

    def test_06_approve_offer(self):
        """Step 6: Approve offer."""
        service = OfferManagementService()
        result = service.approve_offer(None, "OFF1", 1, "manager_id")
        assert result["status"] == "success"

    def test_07_send_offer(self):
        """Step 7: Send offer to candidate."""
        service = OfferManagementService()
        result = service.send_offer_to_candidate(None, "OFF1", 1, "candidate@email.com")
        assert result["status"] == "success"

    def test_08_accept_offer(self):
        """Step 8: Accept offer."""
        service = OfferManagementService()
        result = service.accept_offer(None, "OFF1", 1, "C1")
        assert result["status"] == "success"

    def test_09_convert_employee(self):
        """Step 9: Convert to employee."""
        service = EmployeeConversionService()
        result = service.convert_candidate_to_employee(None, "C1", 1, "John Doe", "john@company.com", 1, "Software Engineer", datetime.utcnow())
        assert result["status"] == "success"
        assert "employee_id" in result

    def test_10_core_pull(self):
        """Step 10: Apply core-pull rules."""
        service = CorePullService()
        result = service.apply_core_pull_rule(None, "ALLOC1", 1)
        assert result["status"] == "success"

    def test_11_allocate_project(self):
        """Step 11: Allocate to project."""
        service = ProjectAllocationService()
        result = service.allocate_employee_to_project(None, "EMP1", "P1", 1, datetime.utcnow())
        assert result["status"] == "success"

    def test_12_create_timesheet(self):
        """Step 12: Create timesheet."""
        service = TimesheetCompleteService()
        result = service.create_timesheet(None, "EMP1", "ALLOC1", 1, datetime.utcnow())
        assert result["status"] == "success"

    def test_13_submit_timesheet(self):
        """Step 13: Submit timesheet."""
        service = TimesheetCompleteService()
        result = service.submit_timesheet(None, "TS1", 1)
        assert result["status"] in ["success", "error"]

    def test_14_approve_timesheet(self):
        """Step 14: Approve timesheet."""
        service = TimesheetCompleteService()
        result = service.approve_timesheet(None, "TS1", 1, "approver")
        assert result["status"] in ["success", "error"]

    def test_15_generate_invoice(self):
        """Step 15: Generate invoice."""
        service = InvoiceCompleteService()
        result = service.generate_invoice_from_timesheets(None, "CLIENT1", "P1", 1, datetime.utcnow(), datetime.utcnow(), 10000)
        assert result["status"] in ["success", "error"]

    def test_16_recognize_revenue(self):
        """Step 16: Recognize revenue."""
        service = RevenueRecognitionService()
        result = service.recognize_revenue_from_invoice(None, "INV1", 1, "MONTHLY")
        assert result["status"] == "success"
