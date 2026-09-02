"""
import logging
HRMS-1105 (S-320) -- Candidate Ranking & Scoring Service Tests.

Test coverage:
- Unit tests for scoring formulas
- Integration tests for full ranking flow
- Edge cases and error handling
"""
import os
import tempfile
import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.tenant import Tenant
from app.services.candidate_scoring_service import CandidateScoringService


@pytest.fixture()
def db_session():
    """Create temporary SQLite database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded_data(db_session):
    """Create test data with candidates and demands."""
    # Create tenant
    tenant = Tenant(tenant_id=1, tenant_name="test-tenant", active=True)
    db_session.add(tenant)
    db_session.flush()

    # Create candidates
    candidates_data = [
        {
            "candidateID": "C001",
            "candidateEmail": "candidate1@example.com",
            "candidatePassword": "hashed_password",
            "candidateFirstName": "John",
            "candidateLastName": "Developer",
            "candidateJobTitle": "Senior Python Developer",
            "candidateSkills": json.dumps(["Python", "Django", "PostgreSQL", "AWS", "Docker"]),
            "total_experience_months": 120,  # 10 years
            "candidateCurrentLocation": "San Francisco, CA",
            "resume_completeness_score": 95,
            "tenant_id": 1,
        },
        {
            "candidateID": "C002",
            "candidateEmail": "candidate2@example.com",
            "candidatePassword": "hashed_password",
            "candidateFirstName": "Jane",
            "candidateLastName": "Engineer",
            "candidateJobTitle": "Full Stack Developer",
            "candidateSkills": json.dumps(["Python", "JavaScript", "React", "Node.js"]),
            "total_experience_months": 72,  # 6 years
            "candidateCurrentLocation": "New York, NY",
            "resume_completeness_score": 85,
            "tenant_id": 1,
        },
        {
            "candidateID": "C003",
            "candidateEmail": "candidate3@example.com",
            "candidatePassword": "hashed_password",
            "candidateFirstName": "Bob",
            "candidateLastName": "Junior",
            "candidateJobTitle": "Junior Developer",
            "candidateSkills": json.dumps(["Python", "Java"]),
            "total_experience_months": 24,  # 2 years
            "candidateCurrentLocation": "Seattle, WA",
            "resume_completeness_score": 60,
            "tenant_id": 1,
        },
        {
            "candidateID": "C004",
            "candidateEmail": "candidate4@example.com",
            "candidatePassword": "hashed_password",
            "candidateFirstName": "Alice",
            "candidateLastName": "Data",
            "candidateJobTitle": "Data Scientist",
            "candidateSkills": json.dumps(["Python", "R", "SQL", "Pandas", "TensorFlow"]),
            "total_experience_months": 84,  # 7 years
            "candidateCurrentLocation": "Remote",
            "resume_completeness_score": 90,
            "tenant_id": 1,
        },
        {
            "candidateID": "C005",
            "candidateEmail": "candidate5@example.com",
            "candidatePassword": "hashed_password",
            "candidateFirstName": "Charlie",
            "candidateLastName": "Frontend",
            "candidateJobTitle": "Frontend Developer",
            # Missing skills - incomplete profile
            "candidateSkills": None,
            "total_experience_months": 60,
            "candidateCurrentLocation": "Austin, TX",
            "resume_completeness_score": None,
            "tenant_id": 1,
        }
    ]

    candidates = [Candidate(**data) for data in candidates_data]
    db_session.add_all(candidates)
    db_session.flush()

    # Create demands (jobs)
    demands_data = [
        {
            "id": "D001",
            "tenant_id": 1,
            "client_id": "CL001",
            "job_title": "Senior Backend Engineer",
            "job_description": "Looking for experienced Python developer with cloud expertise",
            "required_skills": json.dumps(["Python", "PostgreSQL", "AWS"]),
            "nice_to_have_skills": json.dumps(["Docker", "Kubernetes", "Microservices"]),
            "min_experience_years": Decimal("5"),
            "max_experience_years": Decimal("15"),
            "work_location": "REMOTE",
            "job_location": "San Francisco, CA",
            "employment_type": "W2_FULLTIME",
            "interview_type_required": "L1_AND_L2",
            "headcount": 1,
            "urgency": "HIGH",
            "status": "OPEN",
        },
        {
            "id": "D002",
            "tenant_id": 1,
            "client_id": "CL002",
            "job_title": "Full Stack Developer",
            "job_description": "Need someone with both frontend and backend skills",
            "required_skills": json.dumps(["Python", "JavaScript", "React"]),
            "nice_to_have_skills": json.dumps(["Node.js", "MongoDB"]),
            "min_experience_years": Decimal("3"),
            "max_experience_years": Decimal("10"),
            "work_location": "HYBRID",
            "job_location": "New York, NY",
            "employment_type": "W2_FULLTIME",
            "interview_type_required": "L1_AND_L2",
            "headcount": 2,
            "urgency": "NORMAL",
            "status": "OPEN",
        },
        {
            "id": "D003",
            "tenant_id": 1,
            "client_id": "CL003",
            "job_title": "Python Django Developer",
            "job_description": "Django specialist needed",
            "required_skills": json.dumps(["Python", "Django"]),
            "nice_to_have_skills": json.dumps(["PostgreSQL"]),
            "min_experience_years": Decimal("2"),
            "max_experience_years": Decimal("8"),
            "work_location": "ONSITE",
            "job_location": "Austin, TX",
            "employment_type": "W2_FULLTIME",
            "interview_type_required": "L1_ONLY",
            "headcount": 1,
            "urgency": "IMMEDIATE",
            "status": "OPEN",
        }
    ]

    demands = [Demand(**data) for data in demands_data]
    db_session.add_all(demands)
    db_session.commit()

    return {
        "candidates": {c.candidateID: c for c in candidates},
        "demands": {d.id: d for d in demands},
        "tenant_id": 1,
    }

logger = logging.getLogger(__name__)

class TestCalculateFitScore:
    """Tests for calculate_fit_score method."""

    def test_calculate_fit_score_strong_match(self, db_session, seeded_data):
        """Test fit score calculation for strong match (C001 -> D001)."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",  # Senior Python Developer
            demand_id="D001",      # Senior Backend Engineer
            tenant_id=1
        )

        assert result["status"] == "success"
        assert result["fit_score"] >= 85, "Strong match should score >= 85"
        assert result["recommendation"] == "STRONG_MATCH"
        assert "components" in result
        assert result["components"]["skills_match"] > 70

    def test_calculate_fit_score_good_match(self, db_session, seeded_data):
        """Test fit score calculation for good match (C002 -> D002)."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C002",  # Full Stack Developer
            demand_id="D002",      # Full Stack Developer
            tenant_id=1
        )

        assert result["status"] == "success"
        assert 70 <= result["fit_score"] < 85, "Good match should score 70-84"
        assert result["recommendation"] == "GOOD_MATCH"

    def test_calculate_fit_score_weak_match(self, db_session, seeded_data):
        """Test fit score calculation for weak match (C003 -> D001)."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C003",  # Junior Developer
            demand_id="D001",      # Senior Backend Engineer
            tenant_id=1
        )

        assert result["status"] == "success"
        # Junior should not score well for senior role
        assert result["fit_score"] < 50, "Junior should not match senior role well"
        assert result["recommendation"] in ["FAIR_MATCH", "WEAK_MATCH"]

    def test_calculate_fit_score_nonexistent_candidate(self, db_session, seeded_data):
        """Test error handling for nonexistent candidate."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="NONEXISTENT",
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "error"
        assert "not found" in result.get("error", "").lower()

    def test_calculate_fit_score_nonexistent_demand(self, db_session, seeded_data):
        """Test error handling for nonexistent demand."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",
            demand_id="NONEXISTENT",
            tenant_id=1
        )

        assert result["status"] == "error"
        assert "not found" in result.get("error", "").lower()

    def test_calculate_fit_score_remote_location_preference(self, db_session, seeded_data):
        """Test that remote jobs match any candidate location."""
        service = CandidateScoringService()

        # Remote job should match anyone
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C002",  # Located in New York
            demand_id="D001",      # Remote job
            tenant_id=1
        )

        assert result["status"] == "success"
        # Location should be perfect for remote
        assert result["components"]["location_match"] == 100

    def test_fit_score_components_sum_correctly(self, db_session, seeded_data):
        """Test that components are weighted correctly."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"

        # Verify weights exist and sum to 100
        weights = result.get("weights", {})
        total_weight = sum(weights.values())
        assert total_weight == 100, f"Weights should sum to 100, got {total_weight}"

        # Verify fit_score is between 0-100
        assert 0 <= result["fit_score"] <= 100


class TestRankCandidates:
    """Tests for rank_candidates method."""

    def test_rank_candidates_returns_ordered_list(self, db_session, seeded_data):
        """Test that candidates are ranked by fit_score descending."""
        service = CandidateScoringService()
        result = service.rank_candidates(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"
        assert "ranked_candidates" in result

        candidates = result["ranked_candidates"]
        assert len(candidates) > 0

        # Verify ordering (descending by fit_score)
        for i in range(len(candidates) - 1):
            current_score = candidates[i]["fit_score"]
            next_score = candidates[i + 1]["fit_score"]
            assert current_score >= next_score, "Candidates should be ordered by fit_score descending"

        # Verify ranks are correct
        for i, candidate in enumerate(candidates, 1):
            assert candidate["rank"] == i, f"Rank should be {i}, got {candidate['rank']}"

    def test_rank_candidates_nonexistent_demand(self, db_session, seeded_data):
        """Test error handling for nonexistent demand."""
        service = CandidateScoringService()
        result = service.rank_candidates(
            db=db_session,
            demand_id="NONEXISTENT",
            tenant_id=1
        )

        assert result["status"] == "error"
        assert "not found" in result.get("error", "").lower()

    def test_rank_candidates_with_limit(self, db_session, seeded_data):
        """Test that limit parameter works correctly."""
        service = CandidateScoringService()
        result = service.rank_candidates(
            db=db_session,
            demand_id="D001",
            tenant_id=1,
            limit=2
        )

        assert result["status"] == "success"
        # Should have at most 2 candidates evaluated
        assert result["total_candidates_evaluated"] <= 2

    def test_rank_candidates_includes_candidate_details(self, db_session, seeded_data):
        """Test that ranked candidates include required details."""
        service = CandidateScoringService()
        result = service.rank_candidates(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"
        if result["ranked_candidates"]:
            candidate = result["ranked_candidates"][0]

            # Verify required fields
            assert "rank" in candidate
            assert "candidate_id" in candidate
            assert "candidate_name" in candidate
            assert "candidate_email" in candidate
            assert "fit_score" in candidate
            assert "recommendation" in candidate
            assert "components" in candidate


class TestIdentifyBestMatch:
    """Tests for identify_best_match method."""

    def test_identify_best_match_returns_top_candidate(self, db_session, seeded_data):
        """Test that best match returns highest-scored candidate."""
        service = CandidateScoringService()

        # Get ranking first
        ranking_result = service.rank_candidates(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        # Get best match
        best_result = service.identify_best_match(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        assert best_result["status"] == "success"
        assert best_result["best_match_candidate_id"] is not None

        # Best match should match top ranked candidate
        if ranking_result["ranked_candidates"]:
            top_ranked = ranking_result["ranked_candidates"][0]
            assert best_result["best_match_candidate_id"] == top_ranked["candidate_id"]
            assert best_result["fit_score"] == top_ranked["fit_score"]

    def test_identify_best_match_ready_to_interview_flag(self, db_session, seeded_data):
        """Test ready_to_interview flag based on fit_score."""
        service = CandidateScoringService()
        result = service.identify_best_match(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"

        # ready_to_interview should be True if fit_score >= 70
        expected_ready = result["fit_score"] >= 70
        assert result["ready_to_interview"] == expected_ready

    def test_identify_best_match_nonexistent_demand(self, db_session, seeded_data):
        """Test error handling for nonexistent demand."""
        service = CandidateScoringService()
        result = service.identify_best_match(
            db=db_session,
            demand_id="NONEXISTENT",
            tenant_id=1
        )

        assert result["status"] == "error"
        assert "not found" in result.get("error", "").lower()

    def test_identify_best_match_includes_candidate_details(self, db_session, seeded_data):
        """Test that best match includes required candidate information."""
        service = CandidateScoringService()
        result = service.identify_best_match(
            db=db_session,
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"

        # Verify required fields
        assert result["best_match_candidate_id"] is not None
        assert result["best_match_candidate_name"] is not None
        assert result["best_match_candidate_email"] is not None
        assert 0 <= result["fit_score"] <= 100
        assert result["recommendation"] in ["STRONG_MATCH", "GOOD_MATCH", "FAIR_MATCH", "WEAK_MATCH"]


class TestComponentScoring:
    """Tests for individual scoring components."""

    def test_skills_match_scoring(self, db_session, seeded_data):
        """Test skills match calculation."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",  # Has Python, Django, PostgreSQL, AWS, Docker
            demand_id="D001",      # Requires Python, PostgreSQL, AWS
            tenant_id=1
        )

        assert result["status"] == "success"
        # C001 has all 3 required skills
        assert result["components"]["skills_match"] == 100

    def test_experience_match_within_range(self, db_session, seeded_data):
        """Test experience score when candidate is within range."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",  # 10 years experience
            demand_id="D001",      # Requires 5-15 years
            tenant_id=1
        )

        assert result["status"] == "success"
        # Should be perfect match
        assert result["components"]["experience_level"] == 100

    def test_experience_match_below_minimum(self, db_session, seeded_data):
        """Test experience score when candidate has less than required."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C003",  # 2 years experience
            demand_id="D001",      # Requires 5+ years
            tenant_id=1
        )

        assert result["status"] == "success"
        # Should be penalized
        assert result["components"]["experience_level"] < 100
        assert result["components"]["experience_level"] > 0

    def test_resume_quality_from_completeness_score(self, db_session, seeded_data):
        """Test that resume_completeness_score is used when available."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",  # Has resume_completeness_score = 95
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"
        # Should use the stored score
        assert result["components"]["resume_completeness"] == 95

    def test_missing_skills_handling(self, db_session, seeded_data):
        """Test handling of candidates with missing skills."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C005",  # Has no candidateSkills
            demand_id="D001",
            tenant_id=1
        )

        assert result["status"] == "success"
        # Should give 0 for skills match
        assert result["components"]["skills_match"] == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_fit_score_boundary_0(self, db_session, seeded_data):
        """Test that fit_score doesn't go below 0."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C005",  # Weak profile
            demand_id="D001",      # Strong requirements
            tenant_id=1
        )

        assert result["status"] == "success"
        assert result["fit_score"] >= 0, "Fit score should never be negative"

    def test_fit_score_boundary_100(self, db_session, seeded_data):
        """Test that fit_score doesn't exceed 100."""
        service = CandidateScoringService()
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C001",  # Strong profile
            demand_id="D001",      # Matching requirements
            tenant_id=1
        )

        assert result["status"] == "success"
        assert result["fit_score"] <= 100, "Fit score should never exceed 100"

    def test_tenant_isolation(self, db_session):
        """Test that candidates from different tenants don't interfere."""
        # Create candidates in different tenants
        tenant1 = Tenant(tenant_id=1, tenant_name="tenant1", active=True)
        tenant2 = Tenant(tenant_id=2, tenant_name="tenant2", active=True)
        db_session.add_all([tenant1, tenant2])
        db_session.flush()

        c1 = Candidate(
            candidateID="C1-T1",
            candidateEmail="c1@tenant1.com",
            candidatePassword="hash",
            candidateFirstName="John",
            candidateSkills=json.dumps(["Python"]),
            total_experience_months=120,
            tenant_id=1
        )

        c2 = Candidate(
            candidateID="C2-T2",
            candidateEmail="c2@tenant2.com",
            candidatePassword="hash",
            candidateFirstName="Jane",
            candidateSkills=json.dumps(["Java"]),
            total_experience_months=60,
            tenant_id=2
        )

        d1 = Demand(
            id="D1-T1",
            tenant_id=1,
            client_id="CL1",
            job_title="Python Dev",
            required_skills=json.dumps(["Python"]),
            min_experience_years=Decimal("3"),
            work_location="REMOTE",
            employment_type="W2_FULLTIME",
            interview_type_required="L1_AND_L2"
        )

        d2 = Demand(
            id="D2-T2",
            tenant_id=2,
            client_id="CL2",
            job_title="Java Dev",
            required_skills=json.dumps(["Java"]),
            min_experience_years=Decimal("2"),
            work_location="REMOTE",
            employment_type="W2_FULLTIME",
            interview_type_required="L1_AND_L2"
        )

        db_session.add_all([c1, c2, d1, d2])
        db_session.commit()

        service = CandidateScoringService()

        # Request should be isolated by tenant
        result = service.calculate_fit_score(
            db=db_session,
            candidate_id="C1-T1",
            demand_id="D2-T2",  # Different tenant's demand
            tenant_id=1
        )

        # Should error because demand doesn't exist in tenant 1
        assert result["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
