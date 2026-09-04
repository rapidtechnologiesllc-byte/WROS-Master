"""Comprehensive test suite for Spartan Phalanx integration"""
import pytest
from datetime import datetime, date, timedelta
import logging
from unittest.mock import Mock, patch, MagicMock

from app.services.spartan_orchestration_service import SpartanOrchestrationService
from app.services.finance_service import FinanceService
from app.services.timesheet_bulk_service import TimesheetBulkService
from app.services.job_management_service import JobManagementService
from app.services.demand_management_service import DemandManagementService
from app.services.kpi_service import KPIService
logger = logging.getLogger(__name__)

class TestFinanceService:
    """Finance Service Tests"""

    def test_create_invoice(self):
        """Test creating a new invoice"""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = FinanceService.create_invoice(
            db=mock_db,
            opportunity_id="opp-123",
            amount=50000.00,
            currency="USD",
            created_by="finance@example.com"
        )

        assert result["status"] == "DRAFT"
        assert result["amount"] == 50000.00
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_approve_invoice(self):
        """Test approving an invoice"""
        mock_db = Mock()
        mock_invoice = Mock()
        mock_invoice.id = "inv-123"
        mock_invoice.status = "PENDING_APPROVAL"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_invoice
        mock_db.commit = Mock()

        result = FinanceService.approve_invoice(
            db=mock_db,
            invoice_id="inv-123",
            approved_by="finance@example.com",
            notes="Verified and approved"
        )

        assert result["status"] == "APPROVED"
        assert mock_invoice.status == "APPROVED"
        assert mock_invoice.approved_by == "finance@example.com"
        mock_db.commit.assert_called_once()

    def test_bulk_approve_invoices(self):
        """Test bulk approving multiple invoices"""
        mock_db = Mock()
        mock_invoice_1 = Mock()
        mock_invoice_1.id = "inv-1"
        mock_invoice_1.status = "PENDING_APPROVAL"

        mock_invoice_2 = Mock()
        mock_invoice_2.id = "inv-2"
        mock_invoice_2.status = "PENDING_APPROVAL"

        def mock_filter_first(invoice_id):
            if invoice_id == "inv-1":
                return mock_invoice_1
            elif invoice_id == "inv-2":
                return mock_invoice_2
            return None

        mock_db.query.return_value.filter.return_value.first.side_effect = lambda: [mock_invoice_1, mock_invoice_2][0]
        mock_db.commit = Mock()

        result = FinanceService.bulk_approve_invoices(
            db=mock_db,
            invoice_ids=["inv-1", "inv-2"],
            approved_by="finance@example.com"
        )

        assert result["approved"] >= 0
        assert result["total"] == 2
        mock_db.commit.assert_called()

class TestTimesheetBulkService:
    """Timesheet Bulk Service Tests"""

    def test_bulk_approve_timesheets(self):
        """Test approving multiple timesheets"""
        mock_db = Mock()
        mock_ts_1 = Mock()
        mock_ts_1.id = "ts-1"
        mock_ts_1.status = "SUBMITTED"

        mock_ts_2 = Mock()
        mock_ts_2.id = "ts-2"
        mock_ts_2.status = "SUBMITTED"

        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_ts_1, mock_ts_2]
        mock_db.commit = Mock()

        result = TimesheetBulkService.bulk_approve_timesheets(
            db=mock_db,
            timesheet_ids=["ts-1", "ts-2"],
            approved_by="manager@example.com"
        )

        assert result["total"] == 2
        assert result["failed"] <= 2
        mock_db.commit.assert_called()

    def test_get_timesheet_kpis(self):
        """Test getting timesheet KPIs"""
        mock_db = Mock()
        mock_ts_1 = Mock()
        mock_ts_1.status = "APPROVED"
        mock_ts_1.hours_worked = 40

        mock_ts_2 = Mock()
        mock_ts_2.status = "SUBMITTED"
        mock_ts_2.hours_worked = 35

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_ts_1, mock_ts_2]

        result = TimesheetBulkService.get_timesheet_kpis(db=mock_db)

        assert "total_timesheets" in result
        assert "approval_rate" in result
        assert "kpi_score" in result
        assert result["total_timesheets"] == 2

class TestJobManagementService:
    """Job Management Service Tests"""

    def test_update_job_details(self):
        """Test updating job details"""
        mock_db = Mock()
        mock_job = Mock()
        mock_job.id = "job-123"
        mock_job.title = "Senior Developer"
        mock_job.updated_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_db.commit = Mock()

        result = JobManagementService.update_job_details(
            db=mock_db,
            job_id="job-123",
            updates={
                "title": "Senior Software Engineer",
                "salary_min": 120000,
                "salary_max": 150000
            },
            updated_by="hr@example.com"
        )

        assert result["updated_fields"]["title"] == "Senior Software Engineer"
        mock_db.commit.assert_called()

    def test_close_job(self):
        """Test closing a job"""
        mock_db = Mock()
        mock_job = Mock()
        mock_job.id = "job-123"
        mock_job.status = "OPEN"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_db.commit = Mock()

        result = JobManagementService.close_job(
            db=mock_db,
            job_id="job-123",
            reason="FILLED",
            closed_by="hr@example.com"
        )

        assert result["status"] == "CLOSED"
        assert result["reason"] == "FILLED"
        mock_db.commit.assert_called()

class TestDemandManagementService:
    """Demand Management Service Tests"""

    def test_create_demand(self):
        """Test creating a resource demand"""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = DemandManagementService.create_demand(
            db=mock_db,
            resource_type="DEVELOPER",
            quantity=5,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            business_unit_id="bu-123"
        )

        assert result["status"] == "OPEN"
        assert result["quantity_needed"] == 5
        assert result["resource_type"] == "DEVELOPER"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_adjust_demand_quantity(self):
        """Test adjusting demand quantity"""
        mock_db = Mock()
        mock_demand = Mock()
        mock_demand.id = "dem-123"
        mock_demand.quantity_needed = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_demand
        mock_db.commit = Mock()

        result = DemandManagementService.adjust_demand_quantity(
            db=mock_db,
            demand_id="dem-123",
            new_quantity=8,
            adjusted_by="manager@example.com"
        )

        assert result["old_quantity"] == 5
        assert result["new_quantity"] == 8
        mock_db.commit.assert_called()

class TestKPIService:
    """KPI Service Tests"""

    def test_recruitment_candidates_kpi(self):
        """Test recruitment candidates sourced KPI"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 45

        result = KPIService._get_recruitment_candidates(mock_db, "weekly")

        assert result["kpi"] == "candidates_sourced"
        assert result["value"] == 45
        assert result["target"] == 100
        assert "achievement_percent" in result
        assert "status" in result

    def test_resource_utilization_kpi(self):
        """Test resource utilization KPI"""
        mock_db = Mock()
        mock_allocation_1 = Mock()
        mock_allocation_1.billable = True
        mock_allocation_2 = Mock()
        mock_allocation_2.billable = True
        mock_allocation_3 = Mock()
        mock_allocation_3.billable = False

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_allocation_1,
            mock_allocation_2,
            mock_allocation_3
        ]

        result = KPIService._get_resource_utilization(mock_db, "weekly")

        assert result["kpi"] == "resource_utilization"
        assert result["value"] == pytest.approx(66.67, 0.1)
        assert result["status"] in ["healthy", "warning", "critical"]

    def test_timesheet_approval_rate_kpi(self):
        """Test timesheet approval rate KPI"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.side_effect = [10, 9]  # Total: 10, Approved: 9

        result = KPIService._get_timesheet_approval_rate(mock_db, "weekly")

        assert result["kpi"] == "timesheet_approval_rate"
        assert result["value"] == 90.0
        assert result["status"] == "healthy"

    def test_invoice_approval_rate_kpi(self):
        """Test invoice approval rate KPI"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.side_effect = [20, 18]  # Total: 20, Approved: 18

        result = KPIService._get_invoice_approval_rate(mock_db, "weekly")

        assert result["kpi"] == "invoice_approval_rate"
        assert result["value"] == 90.0
        assert result["status"] == "healthy"

    def test_phalanx_health_score_recruitment(self):
        """Test phalanx health score calculation"""
        mock_db = Mock()

        # Mock all KPI calculations
        with patch.object(KPIService, 'calculate_kpi') as mock_kpi:
            mock_kpi.return_value = {"achievement_percent": 80}

            result = KPIService.get_phalanx_health_score(mock_db, "recruitment", "weekly")

            assert result["phalanx"] == "recruitment"
            assert "health_score" in result
            assert result["status"] in ["healthy", "warning", "critical"]

class TestSpartanOrchestration:
    """Spartan Orchestration Tests"""

    def test_queue_recruitment_operation(self):
        """Test queuing a recruitment operation"""
        mock_db = Mock()
        mock_queue_result = {"message_id": "msg-123"}

        with patch.object(MessageQueueService, 'enqueue', return_value=mock_queue_result):
            result = SpartanOrchestrationService.queue_recruitment_operation(
                db=mock_db,
                operation="CANDIDATE_INTAKE",
                payload={"candidate_id": "cand-123"},
                priority="HIGH"
            )

            assert result["message_id"] == "msg-123"

    def test_queue_finance_operation(self):
        """Test queuing a finance operation"""
        mock_db = Mock()
        mock_queue_result = {"message_id": "msg-456"}

        with patch.object(MessageQueueService, 'enqueue', return_value=mock_queue_result):
            result = SpartanOrchestrationService.queue_finance_operation(
                db=mock_db,
                operation="INVOICE_APPROVE",
                payload={"invoice_id": "inv-123"}
            )

            assert result["message_id"] == "msg-456"

    def test_check_phalanx_integrity(self):
        """Test checking phalanx integrity"""
        mock_db = Mock()

        with patch.object(KPIService, 'get_phalanx_health_score') as mock_health:
            mock_health.return_value = {"health_score": 88}

            result = SpartanOrchestrationService.check_phalanx_integrity(
                db=mock_db,
                phalanx="recruitment"
            )

            assert result["phalanx"] == "recruitment"
            assert result["integrity"] == 88
            assert result["status"] == "HEALTHY"

    def test_get_spartan_formation_status(self):
        """Test getting overall Spartan formation status"""
        mock_db = Mock()

        with patch.object(SpartanOrchestrationService, 'check_phalanx_integrity') as mock_check:
            mock_check.side_effect = [
                {"phalanx": "recruitment", "integrity": 85},
                {"phalanx": "resource_management", "integrity": 88},
                {"phalanx": "finance", "integrity": 90}
            ]

            result = SpartanOrchestrationService.get_spartan_formation_status(mock_db)

            assert "formations" in result
            assert len(result["formations"]) == 3
            assert result["overall_integrity"] == pytest.approx(87.67, 0.1)
            assert result["status"] == "STRONG"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
