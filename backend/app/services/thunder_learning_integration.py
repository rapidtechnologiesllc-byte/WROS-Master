"""Thunder Learning Integration - Wire outcome tracking into outreach decisions

Every time Thunder sends a message, it makes a PREDICTION:
- Predicted outcome: "engagement" (candidate opens/responds within 24h)
- Predicted probability: Confidence score based on channel + history
- Factors: channel_type, time_of_day, recency, segment_type, etc.

Later, when we get delivery/open/click events:
- Record actual outcome: "email_opened", "sms_opened", "no_response", etc.
- Measure confidence_gap = |predicted - actual|
- Update Thunder weights for next cycle
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.services.learning_event_collector import LearningEventCollector
from app.services.learning_handler_integration import LearningIntegrationHelper

logger = logging.getLogger(__name__)


class ThunderLearningIntegration:
    """Integration point between Thunder outreach and autonomous learning system."""

    THUNDER_MODULE = "thunder"
    ENGAGEMENT_OUTCOME = "engagement"
    NO_ENGAGEMENT_OUTCOME = "no_engagement"

    # Expected timeframe for outcome feedback (varies by channel)
    EXPECTED_OUTCOME_TIMEFRAMES = {
        "whatsapp": 24 * 60 * 60,  # 24 hours
        "email": 48 * 60 * 60,     # 48 hours
        "sms": 12 * 60 * 60,       # 12 hours
        "web_chat": 6 * 60 * 60,   # 6 hours
    }

    @staticmethod
    def record_outreach_prediction(
        db: Session,
        tenant_id: str,
        candidate: Candidate,
        conversation: CandidateConversation,
        channel: str,
        message_body: str,
        confidence_score: float,
        segment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record when Thunder sends an outreach message.

        This is the PREDICTION side:
        - We predict the candidate will engage (open/respond)
        - We have a confidence score based on factors
        - Later we'll measure if prediction was correct

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate: Candidate being contacted
            conversation: Conversation thread
            channel: "whatsapp", "email", "sms", "web_chat"
            message_body: Message content
            confidence_score: Our confidence 0.0-1.0
            segment_id: Segment for learning (e.g., "senior_engineer_us")

        Returns:
            Event record with learning_decision_id for later outcome recording
        """
        try:
            # Calculate expected outcome timeframe
            expected_outcome_timestamp = None
            timeframe_seconds = ThunderLearningIntegration.EXPECTED_OUTCOME_TIMEFRAMES.get(
                channel, 24 * 60 * 60
            )
            if timeframe_seconds:
                from datetime import timedelta
                expected_outcome_timestamp = datetime.utcnow() + timedelta(seconds=timeframe_seconds)

            # Build factors that drove this confidence score
            factors_used = LearningIntegrationHelper.extract_decision_metadata_from_handler(
                handler_name="send_thunder_message",
                message={
                    "type": "outreach",
                    "id": str(conversation.id),
                    "channel": channel,
                    "message_length": len(message_body),
                },
                context={
                    "candidate_id": candidate.candidateID,
                    "conversation_id": str(conversation.id),
                    "channel": channel,
                    "segment": segment_id or "unknown",
                }
            )

            # Record the prediction event
            event = LearningEventCollector.record_event(
                db=db,
                tenant_id=tenant_id,
                module=ThunderLearningIntegration.THUNDER_MODULE,
                action_type="outreach_sent",
                entity_type="candidate",
                entity_id=candidate.candidateID,
                secondary_entity_id=str(conversation.id),
                predicted_outcome=ThunderLearningIntegration.ENGAGEMENT_OUTCOME,
                predicted_probability=confidence_score,
                segment_id=segment_id,
                cascade_source=None,
                factors_used={"channel": channel, "confidence_factors": factors_used},
                predicted_metadata={
                    "channel": channel,
                    "message_length": len(message_body),
                    "message_preview": message_body[:50],
                    "time_of_day": datetime.utcnow().hour,
                },
                event_timestamp=datetime.utcnow(),
                expected_outcome_timestamp=expected_outcome_timestamp,
            )

            logger.info(
                f"[ThunderLearning] Recorded outreach prediction: "
                f"candidate={candidate.candidateID} "
                f"channel={channel} "
                f"confidence={confidence_score:.2f}"
            )

            return event

        except Exception as e:
            logger.error(f"[ThunderLearning] Failed to record outreach prediction: {e}", exc_info=True)
            # Don't fail the outreach - learning is async/best-effort
            return {"status": "error", "error": str(e)}

    @staticmethod
    def record_engagement_outcome(
        db: Session,
        tenant_id: str,
        candidate_id: str,
        conversation_id: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Record actual engagement outcome when we get delivery/open/click event.

        Called when:
        - Message delivered (confirm message reached recipient)
        - Message opened (email open, SMS read, WhatsApp read receipt)
        - Message clicked/responded (link click, SMS reply, WhatsApp response)

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            conversation_id: Conversation ID (from original prediction)
            event_type: "delivered", "opened", "clicked", "replied", "no_response"
            event_data: Event details (timestamp, channel, etc.)

        Returns:
            Outcome record with gap measurement
        """
        try:
            # Determine success based on event type
            # "opened" or "replied" = success (engagement)
            # "no_response" after timeframe = failure
            actual_success = event_type in ["opened", "clicked", "replied", "engaged"]

            event = LearningEventCollector.record_event(
                db=db,
                tenant_id=tenant_id,
                module=ThunderLearningIntegration.THUNDER_MODULE,
                action_type="engagement_outcome",
                entity_type="candidate",
                entity_id=candidate_id,
                secondary_entity_id=conversation_id,
                actual_outcome=event_type,
                actual_success=actual_success,
                actual_metadata={
                    "event_type": event_type,
                    "event_timestamp": event_data.get("timestamp"),
                    "channel": event_data.get("channel"),
                    "delay_hours": (datetime.utcnow() - datetime.fromisoformat(
                        event_data.get("timestamp", "")
                    )).total_seconds() / 3600 if event_data.get("timestamp") else None,
                },
                event_timestamp=datetime.utcnow(),
            )

            logger.info(
                f"[ThunderLearning] Recorded engagement outcome: "
                f"candidate={candidate_id} "
                f"outcome={event_type} "
                f"success={actual_success}"
            )

            return event

        except Exception as e:
            logger.error(f"[ThunderLearning] Failed to record engagement outcome: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @staticmethod
    def get_outreach_confidence(
        db: Session,
        candidate: Candidate,
        channel: str,
        segment_id: Optional[str] = None,
    ) -> float:
        """
        Get Thunder's confidence score for outreach success on this channel.

        Pulled from learned patterns (updated every 50 outreach operations).
        Falls back to baseline if no learning yet.

        Args:
            db: Database session
            candidate: Candidate to contact
            channel: Channel type
            segment_id: Segment if applicable

        Returns:
            Confidence score 0.0-1.0
        """
        try:
            if not segment_id:
                # Infer segment from candidate profile if not provided
                segment_id = ThunderLearningIntegration._infer_segment(candidate)

            # Get learned weights for this segment + channel combination
            from app.services.learning_event_collector import LearningEventCollector
            profile = LearningEventCollector.get_segment_profile(
                db=db,
                tenant_id=candidate.tenant_id,
                module=ThunderLearningIntegration.THUNDER_MODULE,
                segment_id=segment_id,
            )

            if profile and profile.get("learned_patterns"):
                patterns = profile.get("learned_patterns", {})
                channel_rates = patterns.get("channel_success_rates", {})
                if channel in channel_rates:
                    return channel_rates[channel]

            # Baseline confidence if no learning yet
            baseline_confidence = {
                "whatsapp": 0.65,  # WhatsApp generally high engagement
                "email": 0.45,     # Email lower engagement
                "sms": 0.55,       # SMS moderate engagement
                "web_chat": 0.70,  # Web chat higher engagement
            }
            return baseline_confidence.get(channel, 0.50)

        except Exception as e:
            logger.warning(f"[ThunderLearning] Failed to get confidence for {channel}: {e}")
            return 0.50  # Conservative default

    @staticmethod
    def _infer_segment(candidate: Candidate) -> str:
        """Infer segment from candidate profile for learning grouping."""
        try:
            # Segment by: seniority_level + location + specialization
            components = []

            if hasattr(candidate, "seniority_level") and candidate.seniority_level:
                components.append(candidate.seniority_level.lower())

            if hasattr(candidate, "current_location") and candidate.current_location:
                # Normalize location
                loc = candidate.current_location.split(",")[0].strip().lower()
                components.append(loc[:2].upper())  # Country/State abbreviation

            if hasattr(candidate, "specialization") and candidate.specialization:
                spec = candidate.specialization.split(";")[0].strip().lower()
                components.append(spec[:8])  # First 8 chars of specialization

            if components:
                return "_".join(components)

            return "unknown"

        except Exception:
            return "unknown"
