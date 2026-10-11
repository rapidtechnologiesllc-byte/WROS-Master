"""End-to-End Test: Thunder Learning Integration
Tests the complete cycle:
1. Thunder sends message → prediction recorded
2. Delivery event arrives → outcome recorded
3. Learning system measures confidence gap and updates weights
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.learning_events import LearningEvent
from app.services.thunder_learning_integration import ThunderLearningIntegration
from app.services.thunder_delivery_outcome_handler import ThunderDeliveryOutcomeHandler
from app.services.learning_event_collector import LearningEventCollector


@pytest.fixture
def test_candidate(db: Session):
    """Create test candidate for learning tests."""
    candidate = Candidate(
        candidateID=str(uuid4()),
        candidateEmail="learning_test@example.com",
        candidateName="Learning Test Candidate",
        tenant_id="test_tenant_123",
        seniority_level="Mid-Level",
        current_location="New York, USA",
        specialization="Python; AWS; DevOps",
    )
    db.add(candidate)
    db.commit()
    return candidate


@pytest.fixture
def test_conversation(db: Session, test_candidate):
    """Create test conversation for learning tests."""
    conversation = CandidateConversation(
        id=uuid4(),
        candidate_id=test_candidate.candidateID,
        conversation_status="active",
    )
    db.add(conversation)
    db.commit()
    return conversation


class TestThunderLearningIntegration:
    """Test Thunder → Learning System integration."""

    def test_record_outreach_prediction(self, db: Session, test_candidate, test_conversation):
        """Test: Record prediction when Thunder sends message."""

        # Thunder decides to send email with 0.75 confidence
        result = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi! We have a role that matches your background.",
            confidence_score=0.75,
            segment_id="mid_level_us_python",
        )

        # Verify event was recorded
        assert result["status"] == "recorded"
        assert "event_id" in result

        # Verify in database
        events = db.query(LearningEvent).filter(
            LearningEvent.entity_id == test_candidate.candidateID
        ).all()

        assert len(events) == 1
        event = events[0]
        assert event.module == "thunder"
        assert event.action_type == "outreach_sent"
        assert event.predicted_outcome == "engagement"
        assert event.predicted_probability == 0.75
        assert event.segment_id == "mid_level_us_python"

    def test_record_engagement_outcome_success(self, db: Session, test_candidate, test_conversation):
        """Test: Record successful engagement outcome."""

        # First: Record the prediction
        prediction = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi! We have a role.",
            confidence_score=0.75,
        )

        # Later: Record the outcome (email opened)
        outcome = ThunderLearningIntegration.record_engagement_outcome(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate_id=test_candidate.candidateID,
            conversation_id=str(test_conversation.id),
            event_type="opened",
            event_data={
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "email",
            },
        )

        assert outcome["status"] == "recorded"

        # Verify outcome event in database
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 1
        event = outcome_events[0]
        assert event.actual_outcome == "opened"
        assert event.actual_success == True

    def test_confidence_gap_calculation(self, db: Session, test_candidate, test_conversation):
        """Test: Confidence gap calculated correctly."""

        # Prediction: 0.75 confidence (expect engagement)
        ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi! We have a role.",
            confidence_score=0.75,
        )

        # Actual: Engagement = True (1.0)
        ThunderLearningIntegration.record_engagement_outcome(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate_id=test_candidate.candidateID,
            conversation_id=str(test_conversation.id),
            event_type="opened",
            event_data={
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "email",
            },
        )

        # Get the outcome event
        outcome_event = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).first()

        # Confidence gap = |0.75 - 1.0| = 0.25
        assert outcome_event.confidence_gap == pytest.approx(0.25, abs=0.01)

    def test_confidence_gap_false_positive(self, db: Session, test_candidate, test_conversation):
        """Test: False positive (predicted engagement, no engagement)."""

        # Prediction: 0.75 confidence (expect engagement)
        ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi! We have a role.",
            confidence_score=0.75,
        )

        # Actual: No engagement
        ThunderLearningIntegration.record_engagement_outcome(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate_id=test_candidate.candidateID,
            conversation_id=str(test_conversation.id),
            event_type="no_response",
            event_data={
                "timestamp": (datetime.utcnow() + timedelta(hours=48)).isoformat(),
                "channel": "email",
            },
        )

        # Get the outcome event
        outcome_event = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).first()

        # Confidence gap = |0.75 - 0.0| = 0.75
        assert outcome_event.confidence_gap == pytest.approx(0.75, abs=0.01)

    def test_delivery_outcome_webhook_email(self, db: Session, test_candidate, test_conversation):
        """Test: Email delivery webhook processing."""

        # Record prediction first
        ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi!",
            confidence_score=0.7,
        )

        # Process email delivery webhook
        webhook_data = {
            "event": "opened",
            "email": test_candidate.candidateEmail,
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": str(test_conversation.id),
            "candidate_id": test_candidate.candidateID,
            "message_id": "msg_123",
            "provider": "sendgrid",
        }

        result = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data,
        )

        assert result["status"] == "recorded"

        # Verify outcome recorded
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 1
        assert outcome_events[0].actual_outcome == "opened"

    def test_delivery_outcome_webhook_sms(self, db: Session, test_candidate, test_conversation):
        """Test: SMS delivery webhook processing."""

        # Record prediction
        ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="sms",
            message_body="Hi! Reply YES to continue.",
            confidence_score=0.65,
        )

        # Process SMS reply webhook
        webhook_data = {
            "event": "replied",
            "phone": "+1234567890",
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": str(test_conversation.id),
            "candidate_id": test_candidate.candidateID,
            "message_id": "sms_456",
            "provider": "twilio",
            "reply_text": "YES",
        }

        result = ThunderDeliveryOutcomeHandler.handle_sms_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data,
        )

        assert result["status"] == "recorded"

        # Verify outcome recorded as "replied"
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 1
        assert outcome_events[0].actual_outcome == "replied"

    def test_segment_inference(self):
        """Test: Segment inference from candidate profile."""

        candidate = Candidate(
            candidateID="test_123",
            candidateName="Test User",
            candidateEmail="test@example.com",
            seniority_level="Senior",
            current_location="San Francisco, USA",
            specialization="Python; Kubernetes; Cloud Architecture",
        )

        segment = ThunderLearningIntegration._infer_segment(candidate)

        # Should infer: senior_us_python (or similar)
        assert "senior" in segment.lower()
        assert "us" in segment.lower() or "san" in segment.lower()

    def test_get_outreach_confidence_baseline(self, db: Session, test_candidate):
        """Test: Baseline confidence when no learning yet."""

        # No learning data exists yet
        confidence = ThunderLearningIntegration.get_outreach_confidence(
            db=db,
            candidate=test_candidate,
            channel="whatsapp",
        )

        # Should return baseline
        assert confidence == 0.65  # WhatsApp baseline


class TestThunderLearningMetrics:
    """Test learning metrics collection and analysis."""

    def test_collect_multiple_outcomes_for_batch(self, db: Session, test_candidate):
        """Test: Collect 50 outcomes for batch analysis."""

        # Create 50 prediction/outcome pairs
        for i in range(50):
            conversation = CandidateConversation(
                id=uuid4(),
                candidate_id=test_candidate.candidateID,
                conversation_status="active",
            )
            db.add(conversation)
            db.flush()

            # Prediction
            ThunderLearningIntegration.record_outreach_prediction(
                db=db,
                tenant_id=test_candidate.tenant_id,
                candidate=test_candidate,
                conversation=conversation,
                channel="email",
                message_body=f"Message {i}",
                confidence_score=0.6 + (i % 20) * 0.01,  # Vary confidence
            )

            # Outcome (about 60% engagement)
            if i % 10 < 6:  # 60% success
                outcome_type = "opened"
                success = True
            else:
                outcome_type = "no_response"
                success = False

            ThunderLearningIntegration.record_engagement_outcome(
                db=db,
                tenant_id=test_candidate.tenant_id,
                candidate_id=test_candidate.candidateID,
                conversation_id=str(conversation.id),
                event_type=outcome_type,
                event_data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "email",
                },
            )

        db.commit()

        # Verify all events recorded
        all_events = db.query(LearningEvent).filter(
            LearningEvent.module == "thunder"
        ).all()

        # Should have: 50 predictions + 50 outcomes = 100 events
        assert len(all_events) == 100

        # Verify outcomes have confidence_gap
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 50
        assert all(e.confidence_gap is not None for e in outcome_events)
