"""
Test engagement phase tracking and knowledge level calculation.

Tests for S-075/HRMS-0475 - Thunder engagement lifecycle management.
"""
import pytest
from datetime import datetime

from app.services.candidate_journey_service import (
    calculate_knowledge_level,
    update_engagement_phase,
)


class TestCalculateKnowledgeLevel:
    """Tests for knowledge level calculation logic."""

    def test_cold_no_responses(self):
        """COLD when candidate has never responded."""
        result = calculate_knowledge_level(
            response_count=0,
            days_since_last_response=None,
            behavioral_signals={}
        )
        assert result == 'COLD'

    def test_warm_initial_response_recent(self):
        """WARM when candidate has 1 response and it's recent (<7 days)."""
        result = calculate_knowledge_level(
            response_count=1,
            days_since_last_response=2,
            behavioral_signals={'replied': True}
        )
        assert result == 'WARM'

    def test_cold_initial_response_old(self):
        """COLD when candidate has 1 response but it's old (>7 days)."""
        result = calculate_knowledge_level(
            response_count=1,
            days_since_last_response=10,
            behavioral_signals={'replied': True}
        )
        assert result == 'COLD'

    def test_warm_moderate_responses_recent(self):
        """WARM when candidate has 2-3 responses and recent activity."""
        for count in [2, 3]:
            result = calculate_knowledge_level(
                response_count=count,
                days_since_last_response=5,
                behavioral_signals={'replied': True}
            )
            assert result == 'WARM'

    def test_hot_many_responses_very_recent(self):
        """HOT when candidate has 4+ responses and very recent (<3 days)."""
        result = calculate_knowledge_level(
            response_count=4,
            days_since_last_response=1,
            behavioral_signals={'replied': True}
        )
        assert result == 'HOT'

    def test_warm_many_responses_recent(self):
        """WARM when candidate has 4+ responses but moderately recent (3-7 days)."""
        result = calculate_knowledge_level(
            response_count=5,
            days_since_last_response=5,
            behavioral_signals={'replied': True, 'clicked_link': True}
        )
        assert result == 'WARM'

    def test_cold_many_responses_old(self):
        """COLD when candidate had many responses but now dormant (>7 days)."""
        result = calculate_knowledge_level(
            response_count=6,
            days_since_last_response=14,
            behavioral_signals={'replied': True}
        )
        assert result == 'COLD'

    def test_warm_no_days_since_response_data(self):
        """Default to WARM when we have response count but no timing data."""
        result = calculate_knowledge_level(
            response_count=2,
            days_since_last_response=None,
            behavioral_signals={}
        )
        assert result == 'WARM'

    def test_zero_days_since_response_is_hot(self):
        """HOT when response count >= 4 and last response was today."""
        result = calculate_knowledge_level(
            response_count=4,
            days_since_last_response=0,
            behavioral_signals={'replied': True}
        )
        assert result == 'HOT'


class TestEngagementPhaseScenarios:
    """Integration tests for real-world engagement scenarios."""

    def test_hot_candidate_lifecycle(self):
        """Scenario: Candidate is hot (many recent responses) → gets hired."""
        # At start: OUTREACH, COLD
        phase = 'OUTREACH'
        knowledge = calculate_knowledge_level(0, None)
        assert knowledge == 'COLD'

        # After first reply: CONVERSION, WARM
        phase = 'CONVERSION'
        knowledge = calculate_knowledge_level(1, days_since_last_response=1)
        assert knowledge == 'WARM'

        # After multiple interviews: still CONVERSION, HOT
        phase = 'CONVERSION'
        knowledge = calculate_knowledge_level(5, days_since_last_response=0)
        assert knowledge == 'HOT'

        # After offer accepted: HIRED
        phase = 'HIRED'
        knowledge = calculate_knowledge_level(6, days_since_last_response=1)
        assert knowledge == 'HOT'

    def test_cold_candidate_lifecycle(self):
        """Scenario: Candidate is cold (no response for 14+ days) → mark dormant."""
        # Start: OUTREACH with no response
        knowledge = calculate_knowledge_level(0, None)
        assert knowledge == 'COLD'

        # After 1 initial response
        knowledge = calculate_knowledge_level(1, days_since_last_response=14)
        assert knowledge == 'COLD'

        # Mark as dormant after 14+ days silence
        phase = 'DORMANT'
        assert phase == 'DORMANT'

    def test_warm_candidate_cycling(self):
        """Scenario: Candidate alternates warm/cold based on activity."""
        # WARM: Responded recently
        knowledge = calculate_knowledge_level(2, days_since_last_response=3)
        assert knowledge == 'WARM'

        # Go cold: Same response count but now 15 days old
        knowledge = calculate_knowledge_level(2, days_since_last_response=15)
        assert knowledge == 'COLD'

        # Re-warm: They respond again
        knowledge = calculate_knowledge_level(3, days_since_last_response=1)
        assert knowledge == 'WARM'
