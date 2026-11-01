"""
End-to-End Test: Webhook → Learning System Integration
Tests the complete flow:
1. Thunder sends message → prediction recorded
2. Webhook arrives from email provider → outcome handler processes it
3. Learning system measures confidence gap and updates weights
"""

import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.candidate import Candidate
from tests import factories
from app.models.candidate_ai import CandidateConversation
from app.models.learning_events import LearningEvent
from app.services.thunder_learning_integration import ThunderLearningIntegration
from app.services.thunder_delivery_outcome_handler import ThunderDeliveryOutcomeHandler


@pytest.fixture
def test_candidate(db: Session):
    """Create test candidate for webhook tests."""
    candidate = factories.candidate(db, candidateEmail=f"webhook-{factories.uid()}@example.com",
                                   candidateExperience="5 years", candidateCurrentLocation="New York, USA",
                                   candidateSkills="Python, AWS, DevOps")
    db.commit()
    return candidate


@pytest.fixture
def test_conversation(db: Session, test_candidate):
    """Create test conversation for webhook tests."""
    # candidate_conversations.tenant_id holds the owning user's UserID (legacy naming)
    owner = factories.user(db)
    conversation = CandidateConversation(
        tenant_id=owner.UserID,
        candidate_id=test_candidate.candidateID,
        status="open",
    )
    db.add(conversation)
    db.commit()
    return conversation


class TestWebhookLearningIntegration:
    """Test complete webhook → learning system integration."""

    def test_sendgrid_webhook_to_learning_flow(self, db: Session, test_candidate, test_conversation):
        """
        Test: Complete flow from SendGrid webhook to learning system.

        Scenario:
        1. Thunder sends email with 0.75 confidence → prediction recorded
        2. SendGrid webhook arrives: email opened
        3. Outcome recorded with confidence_gap = |0.75 - 1.0| = 0.25
        """
        # Step 1: Thunder sends email and records prediction
        prediction = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Hi! Check out this opportunity.",
            confidence_score=0.75,
            segment_id="mid_level_us_python",
        )

        assert prediction["status"] == "recorded"
        prediction_event_id = prediction["event_id"]

        # Verify prediction was recorded
        prediction_event = db.query(LearningEvent).filter(
            LearningEvent.id == prediction_event_id
        ).first()

        assert prediction_event is not None
        assert prediction_event.predicted_probability == 0.75
        assert prediction_event.predicted_outcome == "engagement"

        # Step 2: SendGrid webhook arrives
        webhook_data = {
            "events": [
                {
                    "event": "opened",
                    "email": test_candidate.candidateEmail,
                    "timestamp": datetime.utcnow().isoformat(),
                    "conversation_id": str(test_conversation.id),
                    "candidate_id": test_candidate.candidateID,
                    "tenant_id": test_candidate.tenant_id,
                    "message_id": "msg_123",
                    "sg_message_id": "sg_msg_123",
                }
            ]
        }

        # Step 3: Process webhook through handler
        # (In production, this happens in background task after 200 response)
        for event in webhook_data["events"]:
            result = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
                db=db,
                tenant_id=test_candidate.tenant_id,
                webhook_data={
                    "event": event["event"],
                    "email": event["email"],
                    "timestamp": event["timestamp"],
                    "conversation_id": event["conversation_id"],
                    "candidate_id": event["candidate_id"],
                    "message_id": event["sg_message_id"],
                    "provider": "sendgrid",
                }
            )

            assert result["status"] == "recorded"

        # Step 4: Verify outcome was recorded with confidence gap
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 1
        outcome_event = outcome_events[0]
        assert outcome_event.actual_outcome == "opened"
        assert outcome_event.actual_success == True
        assert outcome_event.confidence_gap == pytest.approx(0.25, abs=0.01)  # |0.75 - 1.0|

    def test_twilio_sms_webhook_to_learning_flow(self, db: Session, test_candidate, test_conversation):
        """
        Test: SMS webhook to learning system.

        Scenario:
        1. Thunder sends SMS with 0.65 confidence → prediction recorded
        2. Twilio webhook arrives: SMS read
        3. Outcome recorded with confidence_gap = |0.65 - 1.0| = 0.35
        """
        # Step 1: Record SMS prediction
        prediction = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="sms",
            message_body="Reply YES to continue.",
            confidence_score=0.65,
        )

        assert prediction["status"] == "recorded"

        # Step 2: Twilio webhook arrives
        webhook_data = {
            "event": "read",
            "To": "+1234567890",
            "From": "+0987654321",
            "MessageSid": "sms_456",
            "Body": "OK",
            "candidate_id": test_candidate.candidateID,
            "conversation_id": str(test_conversation.id),
            "tenant_id": test_candidate.tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Step 3: Process webhook
        result = ThunderDeliveryOutcomeHandler.handle_sms_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data
        )

        assert result["status"] == "recorded"

        # Step 4: Verify outcome was recorded
        outcome_events = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcome_events) == 1
        outcome_event = outcome_events[0]
        assert outcome_event.actual_outcome == "opened"  # "read" maps to "opened"
        assert outcome_event.confidence_gap == pytest.approx(0.35, abs=0.01)

    def test_webhook_missing_required_fields(self, db: Session, test_candidate):
        """
        Test: Webhook missing required fields → error response.

        Should return error without crashing, allowing webhook provider to retry.
        """
        webhook_data = {
            "event": "opened",
            "email": test_candidate.candidateEmail,
            # Missing: candidate_id, conversation_id
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": "msg_789",
        }

        result = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data
        )

        # Should return error, not crash
        assert result["status"] == "error"
        assert "reason" in result or "error" in result

    def test_multiple_webhooks_same_candidate(self, db: Session, test_candidate, test_conversation):
        """
        Test: Multiple webhooks for same candidate → all recorded independently.

        Scenario:
        1. Send email #1 (0.75 confidence) → open → confidence_gap = 0.25
        2. Send email #2 (0.82 confidence) → no response → confidence_gap = 0.82
        """
        # Email #1
        pred1 = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Email 1",
            confidence_score=0.75,
        )

        # Email #1 outcome
        ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data={
                "event": "opened",
                "email": test_candidate.candidateEmail,
                "timestamp": datetime.utcnow().isoformat(),
                "conversation_id": str(test_conversation.id),
                "candidate_id": test_candidate.candidateID,
                "message_id": "msg_1",
                "provider": "sendgrid",
            }
        )

        # Email #2
        pred2 = ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Email 2",
            confidence_score=0.82,
        )

        # Email #2 outcome: No response (implicit failure)
        ThunderLearningIntegration.record_engagement_outcome(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate_id=test_candidate.candidateID,
            conversation_id=str(test_conversation.id),
            event_type="no_response",
            event_data={
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "email",
            }
        )

        # Verify both outcomes recorded
        outcomes = db.query(LearningEvent).filter(
            LearningEvent.action_type == "engagement_outcome"
        ).all()

        assert len(outcomes) == 2

        # Email #1: opened (success)
        outcome1 = [o for o in outcomes if o.actual_outcome == "opened"][0]
        assert outcome1.confidence_gap == pytest.approx(0.25, abs=0.01)

        # Email #2: no_response (failure)
        outcome2 = [o for o in outcomes if o.actual_outcome == "no_response"][0]
        assert outcome2.confidence_gap == pytest.approx(0.82, abs=0.01)

    def test_outreaches_in_the_same_clock_tick_answer_in_order(self, db: Session, test_candidate, test_conversation):
        """Two outreaches stamped in one clock tick (a Windows tick is ~15 ms) must not tie: the
        outcome answers the second one, never an arbitrary one of the two."""
        frozen = datetime(2026, 11, 1, 12, 0, 0)
        with patch("app.services.thunder_learning_integration.datetime") as clock:
            clock.utcnow.return_value = frozen
            clock.fromisoformat = datetime.fromisoformat
            for confidence in (0.75, 0.82):
                ThunderLearningIntegration.record_outreach_prediction(
                    db=db, tenant_id=test_candidate.tenant_id, candidate=test_candidate,
                    conversation=test_conversation, channel="email", message_body="Email",
                    confidence_score=confidence)
            result = ThunderLearningIntegration.record_engagement_outcome(
                db=db, tenant_id=test_candidate.tenant_id, candidate_id=test_candidate.candidateID,
                conversation_id=str(test_conversation.id), event_type="no_response",
                event_data={"channel": "email"})
        assert result["status"] == "recorded"
        outcome = db.query(LearningEvent).filter(LearningEvent.action_type == "engagement_outcome",
                                                 LearningEvent.entity_id == test_candidate.candidateID).one()
        assert outcome.predicted_probability == pytest.approx(0.82)

    def test_webhook_event_deduplication(self, db: Session, test_candidate, test_conversation):
        """
        Test: Same webhook event sent twice → second one should be deduplicated.

        This prevents double-counting in learning system.
        """
        # Send email and record prediction
        ThunderLearningIntegration.record_outreach_prediction(
            db=db,
            tenant_id=test_candidate.tenant_id,
            candidate=test_candidate,
            conversation=test_conversation,
            channel="email",
            message_body="Test email",
            confidence_score=0.75,
        )

        webhook_data = {
            "event": "opened",
            "email": test_candidate.candidateEmail,
            "timestamp": datetime.utcnow().isoformat(),
            "conversation_id": str(test_conversation.id),
            "candidate_id": test_candidate.candidateID,
            "message_id": "msg_duplicate",
            "provider": "sendgrid",
        }

        # Send webhook twice
        result1 = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data
        )
        assert result1["status"] == "recorded"

        # Second webhook (duplicate) - should handle gracefully
        result2 = ThunderDeliveryOutcomeHandler.handle_email_delivery_webhook(
            db=db,
            tenant_id=test_candidate.tenant_id,
            webhook_data=webhook_data
        )

        # TODO: Implement idempotency key deduplication
        # For now, just verify both go through without crashing
        assert result2["status"] in ["recorded", "duplicate"]


TWILIO_TOKEN = "test-twilio-auth-token"
PUBLIC_BASE = "https://hrms.example.test/api"


@pytest.fixture
def sendgrid_key(monkeypatch):
    """A throwaway SendGrid signing key pair; the server is configured with its public half."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    public_der = private.public_key().public_bytes(serialization.Encoding.DER,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setenv("SENDGRID_WEBHOOK_PUBLIC_KEY", base64.b64encode(public_der).decode())
    return private


def _sendgrid_headers(private_key, body: bytes) -> dict:
    import base64
    import time

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    timestamp = str(int(time.time()))
    signature = private_key.sign(timestamp.encode() + body, ec.ECDSA(hashes.SHA256()))
    return {"content-type": "application/json",
            "X-Twilio-Email-Event-Webhook-Signature": base64.b64encode(signature).decode(),
            "X-Twilio-Email-Event-Webhook-Timestamp": timestamp}


@pytest.fixture
def twilio_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_TOKEN)
    monkeypatch.setenv("WEBHOOK_PUBLIC_BASE_URL", PUBLIC_BASE)


def _twilio_signature(path: str, form: dict) -> str:
    import base64
    import hashlib
    import hmac

    data = PUBLIC_BASE + path + "".join(f"{k}{form[k]}" for k in sorted(form))
    return base64.b64encode(hmac.new(TWILIO_TOKEN.encode(), data.encode(), hashlib.sha1).digest()).decode()


class TestWebhookEndpoints:
    """The HTTP endpoints: providers' signatures are the only authentication, fail closed."""

    def test_signed_sendgrid_webhook_is_received(self, client: TestClient, test_candidate, test_conversation,
                                                 sendgrid_key):
        body = json.dumps([{
            "event": "open", "email": test_candidate.candidateEmail,
            "timestamp": int(datetime.utcnow().timestamp()), "conversation_id": str(test_conversation.id),
            "candidate_id": test_candidate.candidateID, "tenant_id": test_candidate.tenant_id,
            "sg_message_id": "sg_123",
        }]).encode()
        response = client.post("/api/v1/webhooks/sendgrid", content=body,
                               headers=_sendgrid_headers(sendgrid_key, body))
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "received"

    def test_unsigned_or_forged_sendgrid_webhook_is_401(self, client: TestClient, sendgrid_key):
        body = b'[{"event": "open"}]'
        assert client.post("/api/v1/webhooks/sendgrid", content=body,
                           headers={"content-type": "application/json"}).status_code == 401
        headers = _sendgrid_headers(sendgrid_key, body)
        assert client.post("/api/v1/webhooks/sendgrid", content=b'[{"event": "click"}]',
                           headers=headers).status_code == 401

    def test_sendgrid_webhook_without_a_configured_key_is_503(self, client: TestClient, monkeypatch):
        monkeypatch.delenv("SENDGRID_WEBHOOK_PUBLIC_KEY", raising=False)
        assert client.post("/api/v1/webhooks/sendgrid", content=b"[]",
                           headers={"content-type": "application/json"}).status_code == 503

    def test_signed_twilio_sms_webhook_is_received(self, client: TestClient, test_candidate, test_conversation,
                                                   twilio_configured):
        form = {"MessageStatus": "read", "To": "+1234567890", "From": "+0987654321", "MessageSid": "sms_123",
                "candidate_id": test_candidate.candidateID, "conversation_id": str(test_conversation.id),
                "tenant_id": str(test_candidate.tenant_id)}
        response = client.post("/api/v1/webhooks/twilio-sms", data=form,
                               headers={"X-Twilio-Signature": _twilio_signature("/api/v1/webhooks/twilio-sms", form)})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "received"

    def test_twilio_webhook_with_a_wrong_signature_is_401(self, client: TestClient, twilio_configured):
        form = {"MessageStatus": "read", "MessageSid": "sms_9"}
        response = client.post("/api/v1/webhooks/twilio-sms", data=form, headers={"X-Twilio-Signature": "forged"})
        assert response.status_code == 401

    def test_signed_non_json_sendgrid_payload_is_ignored_not_retried(self, client: TestClient, sendgrid_key):
        body = b"not valid json"
        response = client.post("/api/v1/webhooks/sendgrid", content=body,
                               headers=_sendgrid_headers(sendgrid_key, body))
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
