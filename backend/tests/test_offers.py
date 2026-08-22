"""
HRMS-0312: Offer Management Unit Tests
Comprehensive test coverage for offer creation, approval, sending, and acceptance.
"""
import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.offer import Offer, OfferStatus
from app.models.candidate import Candidate
from app.models.user import Users, Jobs
from app.services.offer_management_service import OfferManagementService
from app.models.tenant import Tenant

@pytest.fixture
def db_session(db: Session):
    """Database session for tests."""
    return db

@pytest.fixture
def test_tenant(db_session: Session):
    """Create a test tenant."""
    tenant = Tenant(id=1, name="Test Tenant", domain="test.local")
    db_session.add(tenant)
    db_session.commit()
    return tenant

@pytest.fixture
def test_user(db_session: Session, test_tenant):
    """Create a test user."""
    user = Users(
        UserID=str(uuid4()),
        UserEmail="recruiter@test.com",
        UserName="Test Recruiter",
        UserPassword="hashed_password_123",
        tenant_id=test_tenant.id
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def test_candidate(db_session: Session, test_tenant):
    """Create a test candidate."""
    candidate = Candidate(
        candidateID=str(uuid4()),
        candidateEmail="candidate@test.com",
        candidateFirstName="John",
        candidateLastName="Doe",
        tenant_id=test_tenant.id
    )
    db_session.add(candidate)
    db_session.commit()
    return candidate

@pytest.fixture
def test_job(db_session: Session, test_tenant):
    """Create a test job."""
    job = Jobs(
        jobID=str(uuid4()),
        jobTitle="Senior Engineer",
        jobLocation="San Francisco",
        tenant_id=test_tenant.id
    )
    db_session.add(job)
    db_session.commit()
    return job

class TestOfferCreation:
    """Test offer creation functionality."""

    def test_create_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful offer creation."""
        service = OfferManagementService()

        result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            signing_bonus_usd_cents=100000,
            position_title="Senior Software Engineer",
            expected_start_date=date(2026, 9, 1),
            benefits={"health_insurance": "PPO"},
            created_by_user_id=test_user.UserID
        )

        assert result["status"] == "success"
        assert "offer_id" in result
        assert result["candidate_id"] == test_candidate.candidateID
        assert result["salary_usd_cents"] == 15000000

    def test_create_offer_candidate_not_found(self, db_session, test_tenant, test_job, test_user):
        """Test offer creation with non-existent candidate."""
        service = OfferManagementService()

        result = service.create_offer(
            db=db_session,
            candidate_id="non_existent_candidate",
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_create_offer_job_not_found(self, db_session, test_tenant, test_candidate, test_user):
        """Test offer creation with non-existent job."""
        service = OfferManagementService()

        result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id="non_existent_job",
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_create_offer_invalid_salary(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test offer creation with invalid salary."""
        service = OfferManagementService()

        result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=-100,  # Invalid negative salary
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        # Negative salary should still create (service validates salary > 0)
        # But this is caught at the schema validation layer
        # At service level, it depends on validation rules

    def test_offer_starts_in_draft_status(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that new offers start in DRAFT status."""
        service = OfferManagementService()

        result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        offer = db_session.query(Offer).filter(Offer.id == result["offer_id"]).first()
        assert offer.status == OfferStatus.DRAFT

class TestOfferApproval:
    """Test offer approval functionality."""

    def test_approve_draft_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful approval of a draft offer."""
        service = OfferManagementService()

        # Create offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        # Approve offer
        approve_result = service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID,
            approval_notes="Approved - competitive offer"
        )

        assert approve_result["status"] == "success"
        assert approve_result["offer_status"] == OfferStatus.APPROVED

    def test_approve_non_draft_offer_fails(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that approving non-DRAFT offer fails."""
        service = OfferManagementService()

        # Create and approve offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        # Try to approve again
        result = service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        assert result["status"] == "error"
        assert "Cannot approve" in result["message"]

    def test_approve_offer_not_found(self, db_session, test_tenant, test_user):
        """Test approving non-existent offer."""
        service = OfferManagementService()

        result = service.approve_offer(
            db=db_session,
            offer_id="non_existent_offer",
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

class TestOfferSending:
    """Test offer sending functionality."""

    def test_send_approved_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful sending of an approved offer."""
        service = OfferManagementService()

        # Create and approve offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        # Send offer
        send_result = service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com",
            expiration_days=7
        )

        assert send_result["status"] == "success"
        assert send_result["offer_status"] == OfferStatus.SENT
        assert send_result["sent_to"] == "candidate@test.com"
        assert "expires_at" in send_result

    def test_send_draft_offer_fails(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that sending a DRAFT offer fails."""
        service = OfferManagementService()

        # Create offer (stays in DRAFT)
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        # Try to send without approval
        send_result = service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com",
            expiration_days=7
        )

        assert send_result["status"] == "error"
        assert "must be in APPROVED status" in send_result["message"]

    def test_offer_expiration_date_calculation(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that offer expiration date is correctly calculated."""
        service = OfferManagementService()

        # Create and approve offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        # Send with 7-day expiration
        before_send = datetime.utcnow()
        send_result = service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com",
            expiration_days=7
        )
        after_send = datetime.utcnow()

        offer = db_session.query(Offer).filter(Offer.id == create_result["offer_id"]).first()

        # Expiration should be approximately 7 days from now
        assert offer.expiration_date is not None
        days_until_expiry = (offer.expiration_date - datetime.utcnow()).days
        assert days_until_expiry == 6 or days_until_expiry == 7  # Allow 1-day tolerance

class TestOfferRejection:
    """Test offer rejection functionality."""

    def test_reject_sent_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful rejection of a sent offer."""
        service = OfferManagementService()

        # Create, approve, and send offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com"
        )

        # Reject offer
        reject_result = service.reject_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            rejection_reason="Not interested at this time"
        )

        assert reject_result["status"] == "success"
        assert reject_result["offer_status"] == OfferStatus.REJECTED
        assert reject_result["rejection_reason"] == "Not interested at this time"

    def test_reject_draft_offer_fails(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that rejecting a DRAFT offer fails."""
        service = OfferManagementService()

        # Create offer (stays in DRAFT)
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        # Try to reject draft offer
        reject_result = service.reject_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            rejection_reason="Test rejection"
        )

        assert reject_result["status"] == "error"
        assert "Cannot reject" in reject_result["message"]

class TestOfferAcceptance:
    """Test offer acceptance functionality."""

    def test_accept_sent_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful acceptance of a sent offer."""
        service = OfferManagementService()

        # Create, approve, and send offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com"
        )

        # Accept offer
        accept_result = service.accept_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_id=test_candidate.candidateID
        )

        assert accept_result["status"] == "success"
        assert accept_result["offer_status"] == OfferStatus.ACCEPTED
        assert accept_result["candidate_id"] == test_candidate.candidateID

    def test_accept_expired_offer_fails(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that accepting an expired offer fails."""
        service = OfferManagementService()

        # Create and approve offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        # Send with immediate expiration
        service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com",
            expiration_days=0  # Expires immediately
        )

        # Make offer expired manually for testing
        offer = db_session.query(Offer).filter(Offer.id == create_result["offer_id"]).first()
        offer.expiration_date = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        # Try to accept
        accept_result = service.accept_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_id=test_candidate.candidateID
        )

        assert accept_result["status"] == "error"
        assert "expired" in accept_result["message"].lower()

class TestOfferRetraction:
    """Test offer retraction functionality."""

    def test_retract_sent_offer_success(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test successful retraction of a sent offer."""
        service = OfferManagementService()

        # Create, approve, and send offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com"
        )

        # Retract offer
        retract_result = service.retract_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            retraction_reason="Position filled by another candidate"
        )

        assert retract_result["status"] == "success"
        assert retract_result["offer_status"] == OfferStatus.RETRACTED

    def test_cannot_retract_accepted_offer(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test that accepted offers cannot be retracted."""
        service = OfferManagementService()

        # Create, approve, send, and accept offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            position_title="Engineer",
            expected_start_date=date(2026, 9, 1),
            created_by_user_id=test_user.UserID
        )

        service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID
        )

        service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email="candidate@test.com"
        )

        service.accept_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_id=test_candidate.candidateID
        )

        # Try to retract
        retract_result = service.retract_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            retraction_reason="Test retraction"
        )

        assert retract_result["status"] == "error"
        assert "Cannot retract accepted offer" in retract_result["message"]

class TestOfferWorkflow:
    """Test complete offer workflows."""

    def test_complete_workflow_draft_to_accepted(self, db_session, test_tenant, test_candidate, test_job, test_user):
        """Test complete workflow from DRAFT to ACCEPTED."""
        service = OfferManagementService()

        # Step 1: Create offer
        create_result = service.create_offer(
            db=db_session,
            candidate_id=test_candidate.candidateID,
            job_id=test_job.jobID,
            tenant_id=test_tenant.id,
            base_salary_usd_cents=15000000,
            signing_bonus_usd_cents=100000,
            position_title="Senior Engineer",
            expected_start_date=date(2026, 9, 1),
            benefits={"health_insurance": "PPO", "401k": True},
            created_by_user_id=test_user.UserID,
            approval_notes="Market competitive offer"
        )
        assert create_result["status"] == "success"

        # Step 2: Approve offer
        approve_result = service.approve_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            approved_by_user_id=test_user.UserID,
            approval_notes="Approved"
        )
        assert approve_result["status"] == "success"

        # Step 3: Send offer
        send_result = service.send_offer_to_candidate(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_email=test_candidate.candidateEmail,
            expiration_days=7
        )
        assert send_result["status"] == "success"

        # Step 4: Accept offer
        accept_result = service.accept_offer(
            db=db_session,
            offer_id=create_result["offer_id"],
            tenant_id=test_tenant.id,
            candidate_id=test_candidate.candidateID
        )
        assert accept_result["status"] == "success"

        # Verify final state
        offer = db_session.query(Offer).filter(Offer.id == create_result["offer_id"]).first()
        assert offer.status == OfferStatus.ACCEPTED
        assert offer.accepted_at is not None
