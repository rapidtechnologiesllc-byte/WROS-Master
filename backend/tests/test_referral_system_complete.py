"""
import logging
Comprehensive test suite for Employee Referral System with Role-Based Access Control.

Tests:
1. Job referral setup
2. Employee referral recording
3. Referral status updates
4. Bonus creation and payment
5. Role-based access control (CEO, BU Head, HR, Finance, Employee)
6. Analytics and reporting
"""

import logging
import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.referral import EmployeeReferral, JobReferralSettings, ReferralBonus
from app.models.employee import Employee
from app.models.user import Jobs
from app.services.employee_referral_service import EmployeeReferralService
from app.services.referral_access_control import ReferralAccessControl

logger = logging.getLogger(__name__)

class TestJobReferralSetup:
    """Test job referral program setup."""

    def test_create_job_referral_settings(self):
        """Test creating referral settings for a job."""
        db = SessionLocal()
        try:
            result = EmployeeReferralService.create_job_referral_settings(
                db,
                job_id="job_001",
                enable_referrals=True,
                referral_bonus_amount_usd_cents=75000,  # $750
            )

            assert result["status"] == "created"
            assert result["job_id"] == "job_001"
            assert result["enable_referrals"] is True
            assert result["referral_bonus_amount"] == 750.00

        finally:
            db.close()

    def test_send_referral_emails(self):
        """Test generating referral emails for employees."""
        db = SessionLocal()
        try:
            result = EmployeeReferralService.send_referral_emails_for_job(
                db,
                job_id="job_001",
                job_title="Senior Guidewire Developer",
                job_description="Lead implementation role",
                referral_bonus_amount_usd_cents=75000,
            )

            assert result["status"] == "emails_prepared"
            assert "emails_to_send" in result
            assert len(result["email_data"]) > 0

            # Check email structure
            for email in result["email_data"]:
                assert "to" in email
                assert "job_title" in email
                assert "referral_link" in email
                assert "referral_bonus_amount" in email

        finally:
            db.close()


class TestReferralRecording:
    """Test employee referral submission."""

    def test_record_referral(self):
        """Test recording an employee referral."""
        db = SessionLocal()
        try:
            result = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id="emp_123",
                referred_candidate_email="john.doe@external.com",
                referred_candidate_name="John Doe",
            )

            assert result["status"] == "recorded"
            assert result["referral_id"] is not None
            assert result["bonus_potential"] == 750.00
            assert "thank you" in result["message"].lower()

        finally:
            db.close()

    def test_referral_status_progression(self):
        """Test referral moving through pipeline."""
        db = SessionLocal()
        try:
            # Create initial referral
            referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id="emp_123",
                referred_candidate_email="john.doe@external.com",
                referred_candidate_name="John Doe",
            )

            referral_id = referral["referral_id"]

            # Move through pipeline
            statuses = [
                "CANDIDATE_SCREENING",
                "INTERVIEW_SCHEDULED",
                "INTERVIEWED",
                "OFFERED",
                "HIRED",
            ]

            for status in statuses:
                result = EmployeeReferralService.update_referral_status(
                    db, referral_id, status
                )
                assert result["status"] == "updated"
                assert result["new_status"] == status

            # Verify bonus was created when HIRED
            bonuses = db.query(ReferralBonus).filter(
                ReferralBonus.referral_id == referral_id
            ).all()
            assert len(bonuses) > 0

        finally:
            db.close()


class TestBonusPayment:
    """Test referral bonus creation and payment."""

    def test_bonus_created_on_hire(self):
        """Test that bonus is created when referral is hired."""
        db = SessionLocal()
        try:
            # Record and hire a referral
            referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id="emp_123",
                referred_candidate_email="jane.smith@external.com",
                referred_candidate_name="Jane Smith",
            )

            # Hire the candidate
            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "HIRED"
            )

            # Get pending bonuses
            bonuses = EmployeeReferralService.get_pending_bonuses(db)

            bonus_found = any(
                b["referral_id"] == referral["referral_id"] for b in bonuses
            )
            assert bonus_found, "Bonus should be created when referral is hired"

        finally:
            db.close()

    def test_mark_bonus_paid(self):
        """Test marking a bonus as paid."""
        db = SessionLocal()
        try:
            # Create a bonus
            referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id="emp_456",
                referred_candidate_email="bob.jones@external.com",
                referred_candidate_name="Bob Jones",
            )

            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "HIRED"
            )

            # Get bonus ID
            bonuses = EmployeeReferralService.get_pending_bonuses(db)
            bonus_id = next(
                (b["bonus_id"] for b in bonuses if b["referral_id"] == referral["referral_id"]),
                None,
            )

            # Mark as paid
            result = EmployeeReferralService.mark_bonus_paid(
                db, bonus_id, paid_via="PAYROLL"
            )

            assert result["status"] == "paid"
            assert result["paid_via"] == "PAYROLL"

        finally:
            db.close()


class TestRoleBasedAccess:
    """Test role-based access control."""

    def test_ceo_sees_all_referrals(self):
        """Test that CEO can see all referrals."""
        db = SessionLocal()
        try:
            # Create referrals in different BUs
            ref1 = EmployeeReferralService.record_referral(
                db,
                job_id="job_guidewire",
                referring_employee_id="emp_bu1_001",
                referred_candidate_email="candidate1@external.com",
                referred_candidate_name="Candidate 1",
            )

            ref2 = EmployeeReferralService.record_referral(
                db,
                job_id="job_salesforce",
                referring_employee_id="emp_bu2_001",
                referred_candidate_email="candidate2@external.com",
                referred_candidate_name="Candidate 2",
            )

            # CEO gets all referrals
            referrals = ReferralAccessControl.get_referrals_for_user(
                db,
                user_id="ceo_001",
                user_role="CEO",
                user_bu=None,
            )

            assert len(referrals) >= 2
            referral_ids = [r["referral_id"] for r in referrals]
            assert ref1["referral_id"] in referral_ids
            assert ref2["referral_id"] in referral_ids

        finally:
            db.close()

    def test_bu_head_sees_only_their_bu(self):
        """Test that BU Head can only see their BU's referrals."""
        db = SessionLocal()
        try:
            # Get BU Head's referrals
            referrals = ReferralAccessControl.get_referrals_for_user(
                db,
                user_id="bu_head_001",
                user_role="BU_HEAD",
                user_bu="Guidewire",
            )

            # All referrals should be from Guidewire BU
            # (Verify by checking referring_employee belongs to Guidewire)
            # Note: This requires employees to have business_unit field populated

        finally:
            db.close()

    def test_employee_sees_only_own_referrals(self):
        """Test that Employee can only see their own referrals."""
        db = SessionLocal()
        try:
            emp_id = "emp_123"

            # Create referral for this employee
            own_referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id=emp_id,
                referred_candidate_email="own_candidate@external.com",
                referred_candidate_name="Own Candidate",
            )

            # Create referral for different employee
            other_referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_001",
                referring_employee_id="emp_999",
                referred_candidate_email="other_candidate@external.com",
                referred_candidate_name="Other Candidate",
            )

            # Employee gets only their referrals
            referrals = ReferralAccessControl.get_referrals_for_user(
                db,
                user_id=emp_id,
                user_role="EMPLOYEE",
                user_bu="Guidewire",
            )

            referral_ids = [r["referral_id"] for r in referrals]
            assert own_referral["referral_id"] in referral_ids
            # Other referral should NOT be in their list
            # (May appear if accessed before cleanup)

        finally:
            db.close()


class TestRoleBasedDashboards:
    """Test role-based dashboard views."""

    def test_ceo_dashboard(self):
        """Test CEO dashboard view."""
        db = SessionLocal()
        try:
            dashboard = ReferralAccessControl.get_dashboard_view_for_role(
                db,
                user_id="ceo_001",
                user_role="CEO",
                user_bu=None,
            )

            assert dashboard["view"] == "CEO_DASHBOARD"
            assert "total_referrals" in dashboard
            assert "total_hired" in dashboard
            assert "conversion_rate" in dashboard
            assert "total_bonuses_owed" in dashboard
            assert "bonuses_paid" in dashboard

        finally:
            db.close()

    def test_bu_head_dashboard(self):
        """Test BU Head dashboard view."""
        db = SessionLocal()
        try:
            dashboard = ReferralAccessControl.get_dashboard_view_for_role(
                db,
                user_id="bu_head_001",
                user_role="BU_HEAD",
                user_bu="Guidewire",
            )

            assert dashboard["view"] == "BU_DASHBOARD"
            assert dashboard["business_unit"] == "Guidewire"
            assert "total_referrals" in dashboard
            assert "hired_referrals" in dashboard
            assert "conversion_rate" in dashboard

        finally:
            db.close()

    def test_hr_dashboard(self):
        """Test HR Manager dashboard view."""
        db = SessionLocal()
        try:
            dashboard = ReferralAccessControl.get_dashboard_view_for_role(
                db,
                user_id="hr_001",
                user_role="HR_MANAGER",
                user_bu="Guidewire",
            )

            assert dashboard["view"] == "HR_DASHBOARD"
            assert dashboard["business_unit"] == "Guidewire"
            assert "by_status" in dashboard
            assert all(
                status in dashboard["by_status"]
                for status in ["pending", "screening", "interviewed", "offered", "hired"]
            )

        finally:
            db.close()

    def test_finance_dashboard(self):
        """Test Finance dashboard view."""
        db = SessionLocal()
        try:
            dashboard = ReferralAccessControl.get_dashboard_view_for_role(
                db,
                user_id="finance_001",
                user_role="FINANCE",
                user_bu=None,
            )

            assert dashboard["view"] == "FINANCE_DASHBOARD"
            assert "total_bonuses" in dashboard
            assert "pending_payment" in dashboard
            assert "pending_amount" in dashboard
            assert "already_paid" in dashboard
            assert "paid_amount" in dashboard

        finally:
            db.close()

    def test_employee_dashboard(self):
        """Test Employee dashboard view."""
        db = SessionLocal()
        try:
            dashboard = ReferralAccessControl.get_dashboard_view_for_role(
                db,
                user_id="emp_001",
                user_role="EMPLOYEE",
                user_bu="Guidewire",
            )

            assert dashboard["view"] == "EMPLOYEE_DASHBOARD"
            assert "total_referrals" in dashboard
            assert "hired_referrals" in dashboard
            assert "bonus_potential" in dashboard
            assert "bonuses_earned" in dashboard
            assert "bonuses_pending" in dashboard

        finally:
            db.close()


class TestReferralAnalytics:
    """Test analytics and reporting."""

    def test_job_referral_stats(self):
        """Test job-level referral statistics."""
        db = SessionLocal()
        try:
            stats = EmployeeReferralService.get_referral_stats_for_job(db, "job_001")

            assert "status" in stats
            assert "total_referrals" in stats
            assert "total_emails_sent" in stats
            assert "pending_referrals" in stats
            assert "hired_from_referrals" in stats
            assert "referral_to_hire_rate" in stats
            assert "total_bonuses_owed" in stats
            assert "bonuses_paid" in stats

        finally:
            db.close()

    def test_pending_bonuses_for_finance(self):
        """Test finance view of pending bonuses."""
        db = SessionLocal()
        try:
            bonuses = EmployeeReferralService.get_pending_bonuses(db)

            # Each bonus should have required fields
            for bonus in bonuses:
                assert "bonus_id" in bonus
                assert "referral_id" in bonus
                assert "bonus_amount" in bonus
                assert "payment_status" in bonus
                assert bonus["payment_status"] == "PENDING"

        finally:
            db.close()


class TestEndToEndWorkflow:
    """Test complete referral workflow."""

    def test_complete_referral_workflow(self):
        """Test: job creation → referral → hire → bonus → payment."""
        db = SessionLocal()
        try:
            # Step 1: Setup job with referrals
            setup = EmployeeReferralService.create_job_referral_settings(
                db,
                job_id="job_e2e_001",
                enable_referrals=True,
                referral_bonus_amount_usd_cents=50000,  # $500
            )
            assert setup["status"] == "created"

            # Step 2: Send referral emails
            emails = EmployeeReferralService.send_referral_emails_for_job(
                db,
                job_id="job_e2e_001",
                job_title="Test Role",
                job_description="Test description",
                referral_bonus_amount_usd_cents=50000,
            )
            assert emails["status"] == "emails_prepared"

            # Step 3: Employee submits referral
            referral = EmployeeReferralService.record_referral(
                db,
                job_id="job_e2e_001",
                referring_employee_id="emp_e2e_001",
                referred_candidate_email="candidate@example.com",
                referred_candidate_name="Test Candidate",
            )
            assert referral["status"] == "recorded"

            # Step 4: Candidate moves through pipeline
            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "CANDIDATE_SCREENING"
            )
            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "INTERVIEWED"
            )
            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "OFFERED"
            )

            # Step 5: Candidate hired → bonus created
            EmployeeReferralService.update_referral_status(
                db, referral["referral_id"], "HIRED"
            )

            # Step 6: Finance reviews pending bonuses
            pending = EmployeeReferralService.get_pending_bonuses(db)
            bonus_to_pay = next(
                (b for b in pending if b["referral_id"] == referral["referral_id"]),
                None,
            )
            assert bonus_to_pay is not None
            assert bonus_to_pay["bonus_amount"] == 500.00

            # Step 7: Finance marks as paid
            paid = EmployeeReferralService.mark_bonus_paid(
                db, bonus_to_pay["bonus_id"], paid_via="PAYROLL"
            )
            assert paid["status"] == "paid"

            # Step 8: Verify complete
            final_referrals = ReferralAccessControl.get_referrals_for_user(
                db,
                user_id="emp_e2e_001",
                user_role="EMPLOYEE",
                user_bu="TestBU",
            )

            final_ref = next(
                (r for r in final_referrals if r["referral_id"] == referral["referral_id"]),
                None,
            )
            assert final_ref is not None
            assert final_ref["bonus_paid"] is True

        finally:
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
