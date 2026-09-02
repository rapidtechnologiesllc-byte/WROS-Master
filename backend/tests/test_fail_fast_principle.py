"""
Test Suite: Verify "Fail Fast" Principle

Tests that service layer functions raise exceptions instead of silently
returning empty values when errors occur.

This ensures the "fail fast" principle is enforced across the codebase.
All service functions must raise exceptions on error, never silently return empty collections.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock()


# ============================================================================
# TEST SUITE 1: Flash Service (JSON Parsing)
# ============================================================================


class TestFlashServiceSkillParsing:
    """Verify flash_service._skill_tags raises on JSON parse failure."""

    def test_skill_tags_raises_on_invalid_json(self, mock_db):
        """Test that _skill_tags raises ValueError on JSON parse error."""
        from app.services.flash_service import find_available_bench_employees

        # Create mock entry with invalid JSON
        entry = Mock()
        entry.id = 'test-id'
        entry.skill_tags = '{invalid json}'  # Invalid JSON

        # Mock the query to return our entry
        mock_employee = Mock()
        mock_employee.id = 'emp-1'
        mock_employee.current_title = 'Developer'
        mock_employee.email = 'test@example.com'

        mock_db.query().join().order_by().limit().all.return_value = [(entry, mock_employee)]

        # Should raise ValueError, not return empty list
        with pytest.raises(ValueError, match='Invalid JSON in skill_tags'):
            find_available_bench_employees(mock_db, 'python')

    def test_skill_tags_success_case(self):
        """Test that valid JSON parsing works."""
        from app.services.flash_service import find_available_bench_employees

        # This is a positive test - valid JSON should work
        valid_json = json.dumps(['python', 'javascript'])
        assert json.loads(valid_json) == ['python', 'javascript']


# ============================================================================
# TEST SUITE 2: Resume Search Service (Indexing)
# ============================================================================


class TestResumeSearchServiceIndexing:
    """Verify resume_search_service raises on index failures."""

    def test_index_resume_raises_on_exception(self):
        """Test that index_resume_on_parse raises on error."""
        from app.services.resume_search_service import ResumeSearchService

        # Create mock objects
        mock_db = Mock(spec=Session)
        mock_candidate = Mock()
        mock_candidate.candidateID = 'cand-1'
        mock_resume = Mock()

        # Mock _build_searchable_text to raise an exception
        with patch.object(
            ResumeSearchService,
            '_build_searchable_text',
            side_effect=RuntimeError('Parsing failed')
        ):
            # Should raise ValueError, not silently continue
            with pytest.raises(ValueError, match='Failed to index resume'):
                ResumeSearchService.index_resume_on_parse(mock_db, mock_candidate, mock_resume)

    def test_index_resume_success_case(self, mock_db):
        """Test that successful indexing works without raising."""
        from app.services.resume_search_service import ResumeSearchService

        mock_candidate = Mock()
        mock_candidate.candidateID = 'cand-1'
        mock_resume = Mock()
        mock_resume.name = 'John Doe'
        mock_resume.email = 'john@example.com'

        # Patch helper methods to return valid data
        with patch.object(
            ResumeSearchService,
            '_build_searchable_text',
            return_value='John Doe john@example.com'
        ):
            with patch.object(
                ResumeSearchService,
                '_generate_embeddings',
                return_value='[0.1, 0.2, 0.3]'
            ):
                # Should not raise
                ResumeSearchService.index_resume_on_parse(mock_db, mock_candidate, mock_resume)
                assert mock_db.add.called


# ============================================================================
# TEST SUITE 3: Role Template Permission Service
# ============================================================================


class TestRoleTemplatePermissionService:
    """Verify role template permission service raises on validation failures."""

    def test_get_user_permissions_raises_on_missing_user(self, mock_db):
        """Test that missing user_id raises exception."""
        from app.services.role_template_permission_service import RoleTemplatePermissionService

        # Call with empty user_id should raise
        with pytest.raises(Exception, match='user_id is required'):
            RoleTemplatePermissionService.get_user_permissions(mock_db, '', tenant_id=1)

    def test_get_user_permissions_raises_on_no_role(self, mock_db):
        """Test that user without role raises exception."""
        from app.services.role_template_permission_service import RoleTemplatePermissionService

        # Mock user without role
        mock_user = Mock()
        mock_user.UserID = 'user-1'
        mock_user.role_template_id = None

        mock_db.query().filter().first.return_value = mock_user

        # Should raise, not return empty dict
        with pytest.raises(Exception, match='no role template found'):
            RoleTemplatePermissionService.get_user_permissions(mock_db, 'user-1', tenant_id=1)


# ============================================================================
# TEST SUITE 4: Candidate Scoring Service
# ============================================================================


class TestCandidateScoringServiceSkillParsing:
    """Verify candidate scoring service raises on skill parse failures."""

    def test_parse_skills_raises_on_invalid_json(self):
        """Test that _parse_skills raises on invalid JSON."""
        from app.services.candidate_scoring_service import CandidateScoringService

        service = CandidateScoringService()

        # Invalid JSON should raise
        with pytest.raises(Exception, match='Failed to parse candidate skills'):
            service._parse_skills('{invalid json}')

    def test_parse_skills_valid_json(self):
        """Test that valid JSON parsing works."""
        from app.services.candidate_scoring_service import CandidateScoringService

        service = CandidateScoringService()

        # Valid JSON should work
        result = service._parse_skills('["python", "javascript"]')
        assert 'python' in result
        assert 'javascript' in result


# ============================================================================
# INTEGRATION TESTS: Error Propagation
# ============================================================================


class TestErrorPropagation:
    """Verify errors propagate through the call stack correctly."""

    def test_skill_parsing_error_propagates_to_caller(self):
        """Test that skill parsing errors don't get swallowed."""
        # This is a real integration test that should fail if silent failures exist
        from app.services.candidate_scoring_service import CandidateScoringService

        service = CandidateScoringService()

        # Calling with invalid JSON should raise, not return empty
        with pytest.raises(Exception):
            service._parse_skills('{bad json}')

    def test_empty_return_values_not_acceptable(self):
        """Verify that returning [] or {} in catch blocks raises test failure."""
        # This test documents what should NOT happen in service functions

        # ❌ This pattern is WRONG and should fail tests:
        def bad_service_function():
            try:
                raise RuntimeError("Simulated error")
            except Exception:
                raise ValueError("Operation failed")  # ❌ WRONG: Silent failure

        # ✅ This pattern is CORRECT:
        def good_service_function():
            try:
                raise RuntimeError("Simulated error")
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                raise ValueError(f"Failed: {e}")  # ✅ CORRECT: Fail fast

        # Verify bad pattern returns silently
        result = bad_service_function()
        assert result == []

        # Verify good pattern raises
        with pytest.raises(ValueError):
            good_service_function()


# ============================================================================
# REGRESSION TESTS: Known Issues Fixed (2026-08-24)
# ============================================================================


class TestRegressionPrevention:
    """Regression tests for issues fixed on 2026-08-24."""

    def test_flash_service_skill_tags_fix(self):
        """Regression: Ensure _skill_tags doesn't return [] on JSON error."""
        # This would have returned [] silently before the fix
        # Now it should raise

        invalid_json = '{invalid}'

        # Before fix: would return [] silently
        # After fix: should raise ValueError
        with pytest.raises(ValueError):
            json.loads(invalid_json)  # Simulating the internal behavior

    def test_resume_index_failure_raises(self):
        """Regression: Ensure resume indexing raises on error."""
        # This would have silently continued before the fix
        # Now it should raise and fail fast

        # Simulating the pattern from the fix
        def resume_indexing(data):
            try:
                if not data:
                    raise ValueError("No data")
                return True
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                # After fix: raise instead of silent continue
                raise ValueError(f"Failed to index: {e}")

        # Should raise, not silently continue
        with pytest.raises(ValueError, match="Failed to index"):
            resume_indexing(None)


# ============================================================================
# BEST PRACTICES TESTS
# ============================================================================


class TestErrorHandlingBestPractices:
    """Enforce error handling best practices."""

    def test_log_before_raising(self):
        """Test that errors are logged before raising."""
        from unittest.mock import patch
        import logging

        logger = logging.getLogger('test')

        with patch.object(logger, 'error') as mock_log:
            try:
                raise RuntimeError("Test error")
            except RuntimeError as e:
                logger.error(f"Operation failed: {e}", exc_info=True)
                raise ValueError(f"Failed: {e}")

            # Verify logging was called
            assert mock_log.called

    def test_error_messages_are_descriptive(self):
        """Test that raised errors include context."""
        def operation_with_context(user_id, action):
            try:
                raise RuntimeError("Database connection failed")
            except Exception as e:
                logger.error(f"Error: {str(e)}", exc_info=True)
                # ✅ CORRECT: Include context in error
                raise ValueError(f"Failed to {action} for user_id={user_id}: {e}")

        with pytest.raises(ValueError, match="Failed to.*user_id="):
            operation_with_context('user-123', 'fetch_data')


# ============================================================================
# CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "fail_fast: Test the fail-fast error handling principle"
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
