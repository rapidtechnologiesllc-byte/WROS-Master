"""
Unit tests for LinkedIn candidate import workflow

Tests cover:
1. URL parsing (various LinkedIn formats)
2. Apollo enrichment success path
3. Open to Work gate (rejection when not open to work)
4. Duplicate detection (email and phone matching)
5. Candidate creation and consent recording
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.services.linkedin_import_service import (
    _parse_linkedin_url,
    _enrich_via_apollo,
    import_linkedin_candidate,
    InvalidLinkedInURL,
    ApolloCandidateNotFound,
    CandidateNotOpenToWork,
    DuplicateCandidateExists,
)
from app.services.apollo_integration import (
    create_mock_apollo_search,
    create_mock_apollo_not_open_to_work,
    create_mock_apollo_empty_result,
)
from app.services.candidate_service import create_candidate_safe

class TestLinkedInURLParsing:
    """Test _parse_linkedin_url() function"""

    def test_parse_full_url(self):
        """Extract profile slug from full LinkedIn URL"""
        url = "https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707"
        result = _parse_linkedin_url(url)
        assert result == "prabhu-ananthanarayanan-989a707"

    def test_parse_short_url(self):
        """Extract profile slug from short URL (no www)"""
        url = "https://linkedin.com/in/jane-doe-12345"
        result = _parse_linkedin_url(url)
        assert result == "jane-doe-12345"

    def test_parse_path_only(self):
        """Extract profile slug from path-only format"""
        url = "/in/john-smith-99999"
        result = _parse_linkedin_url(url)
        assert result == "john-smith-99999"

    def test_parse_invalid_format(self):
        """Reject invalid LinkedIn URL format"""
        url = "https://linkedin.com/company/some-company"
        with pytest.raises(InvalidLinkedInURL):
            _parse_linkedin_url(url)

    def test_parse_empty_url(self):
        """Reject empty URL"""
        with pytest.raises(InvalidLinkedInURL):
            _parse_linkedin_url("")

class TestApolloEnrichment:
    """Test _enrich_via_apollo() function"""

    @pytest.mark.asyncio
    async def test_enrich_success(self):
        """Successfully enrich candidate data from Apollo"""
        mock_apollo = create_mock_apollo_search(
            email="prabhu@example.com",
            phone="+1-555-0123456",
            full_name="Prabhu Ananthanarayanan",
            company="TechCorp Inc",
            title="Senior Software Engineer",
            open_to_work=True,
        )

        result = await _enrich_via_apollo(
            "prabhu-ananthanarayanan-989a707",
            apollo_search_func=mock_apollo
        )

        assert result['email'] == "prabhu@example.com"
        assert result['phone'] == "+1-555-0123456"
        assert result['full_name'] == "Prabhu Ananthanarayanan"
        assert result['company'] == "TechCorp Inc"
        assert result['title'] == "Senior Software Engineer"
        assert result['open_to_work'] is True

    @pytest.mark.asyncio
    async def test_enrich_gate_rejects_not_open_to_work(self):
        """Reject candidates NOT marked Open to Work (CRITICAL GATE)"""
        mock_apollo = create_mock_apollo_not_open_to_work(
            email="passive@example.com",
            full_name="Passive Candidate"
        )

        with pytest.raises(CandidateNotOpenToWork):
            await _enrich_via_apollo(
                "some-profile-slug",
                apollo_search_func=mock_apollo
            )

    @pytest.mark.asyncio
    async def test_enrich_handles_empty_result(self):
        """Handle case where Apollo returns no contacts"""
        mock_apollo = create_mock_apollo_empty_result()

        with pytest.raises(ApolloCandidateNotFound):
            await _enrich_via_apollo(
                "unknown-profile",
                apollo_search_func=mock_apollo
            )

    @pytest.mark.asyncio
    async def test_enrich_missing_apollo_function(self):
        """Raise error if apollo_search_func not provided"""
        with pytest.raises(ValueError, match="dependency injection required"):
            await _enrich_via_apollo("some-profile", apollo_search_func=None)

class TestLinkedInCandidateImport:
    """Integration tests for complete import workflow"""

    @pytest.mark.asyncio
    async def test_complete_import_flow(self, db: Session):
        """End-to-end test: URL → Candidate → Ready for Thunder"""
        mock_apollo = create_mock_apollo_search(
            email="testuser@example.com",
            phone="+1-555-9876543",
            full_name="Test User",
            company="Test Company",
            title="Test Engineer",
            open_to_work=True,
        )

        candidate, import_info = await import_linkedin_candidate(
            db,
            "https://www.linkedin.com/in/test-user-12345",
            apollo_search_func=mock_apollo,
            promoted_by="system_test",
            now=datetime.utcnow(),
        )

        # Verify candidate was created
        assert candidate is not None
        assert candidate.candidateID is not None
        assert candidate.candidateEmail == "testuser@example.com"
        assert candidate.candidateMobileNumber == "+1-555-9876543"

        # Verify import info returned correctly
        assert import_info['status'] == 'SUCCESS'
        assert import_info['candidate_id'] == candidate.candidateID
        assert import_info['email'] == "testuser@example.com"
        assert import_info['phone'] == "+1-555-9876543"
        assert import_info['open_to_work'] is True

        # Verify consent was recorded
        consent = db.query(ConsentRecord).filter(
            ConsentRecord.subject_id == candidate.candidateID,
            ConsentRecord.consent_type == "whatsapp_outreach",
        ).first()
        assert consent is not None
        assert consent.consent_given is True

    @pytest.mark.asyncio
    async def test_import_rejects_not_open_to_work(self, db: Session):
        """Import should reject candidates not marked Open to Work"""
        mock_apollo = create_mock_apollo_not_open_to_work()

        with pytest.raises(CandidateNotOpenToWork):
            await import_linkedin_candidate(
                db,
                "https://www.linkedin.com/in/some-user",
                apollo_search_func=mock_apollo,
                promoted_by="system_test",
            )

    @pytest.mark.asyncio
    async def test_import_handles_duplicate_email(self, db: Session):
        """Import should reject if candidate with same email exists"""
        # Create first candidate
        existing = create_candidate_safe(
            db,
            email="duplicate@example.com",
            mobile="+1-555-0000000",
        )

        # Try to import another with same email
        mock_apollo = create_mock_apollo_search(
            email="duplicate@example.com",
            phone="+1-555-1111111",  # Different phone
            full_name="Same Email User",
            open_to_work=True,
        )

        with pytest.raises(DuplicateCandidateExists):
            await import_linkedin_candidate(
                db,
                "https://www.linkedin.com/in/different-user",
                apollo_search_func=mock_apollo,
                promoted_by="system_test",
            )

    @pytest.mark.asyncio
    async def test_import_handles_duplicate_phone(self, db: Session):
        """Import should reject if candidate with same phone exists"""
        # Create first candidate
        existing = create_candidate_safe(
            db,
            email="email1@example.com",
            mobile="+1-555-5555555",
        )

        # Try to import another with same phone
        mock_apollo = create_mock_apollo_search(
            email="email2@example.com",
            phone="+1-555-5555555",  # Same phone as existing
            full_name="Same Phone User",
            open_to_work=True,
        )

        with pytest.raises(DuplicateCandidateExists):
            await import_linkedin_candidate(
                db,
                "https://www.linkedin.com/in/different-user",
                apollo_search_func=mock_apollo,
                promoted_by="system_test",
            )

    @pytest.mark.asyncio
    async def test_import_invalid_url(self, db: Session):
        """Import should reject invalid LinkedIn URLs"""
        mock_apollo = create_mock_apollo_search()

        with pytest.raises(InvalidLinkedInURL):
            await import_linkedin_candidate(
                db,
                "https://twitter.com/someone",  # Wrong platform
                apollo_search_func=mock_apollo,
                promoted_by="system_test",
            )

class TestApolloIntegration:
    """Test Apollo integration module"""

    @pytest.mark.asyncio
    async def test_mock_apollo_success(self):
        """Verify mock Apollo returns correct structure"""
        mock_apollo = create_mock_apollo_search(
            email="test@example.com",
            phone="+1-555-1234567",
            full_name="Test Person",
            company="Test Corp",
            title="Test Role",
            open_to_work=True,
        )

        result = await mock_apollo({"linkedin_url": "https://www.linkedin.com/in/test"})

        assert 'contacts' in result
        assert len(result['contacts']) == 1
        assert result['contacts'][0]['email'] == "test@example.com"
        assert result['contacts'][0]['phone_number'] == "+1-555-1234567"
        assert result['contacts'][0]['open_to_work_status'] is True

    @pytest.mark.asyncio
    async def test_mock_apollo_not_open_to_work(self):
        """Verify mock returns not open to work status"""
        mock_apollo = create_mock_apollo_not_open_to_work()

        result = await mock_apollo({"linkedin_url": "https://www.linkedin.com/in/test"})

        assert result['contacts'][0]['open_to_work_status'] is False

    @pytest.mark.asyncio
    async def test_mock_apollo_empty_result(self):
        """Verify mock returns empty contacts list"""
        mock_apollo = create_mock_apollo_empty_result()

        result = await mock_apollo({"linkedin_url": "https://www.linkedin.com/in/unknown"})

        assert result['contacts'] == []
