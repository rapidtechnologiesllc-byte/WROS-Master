"""
import logging
Relation Building Interaction Tracker - Continuous Persona Learning

Captures and analyzes EVERY candidate interaction to continuously update persona:
- Email responses (timing, tone, engagement)
- WhatsApp/SMS messages (responsiveness, enthusiasm)
- AI Recruiter conversations (stated preferences, objections, interest level)
- Interview feedback (performance, fit, enthusiasm)
- Offer responses (negotiation, enthusiasm, speed)
- Joining signals (engagement, commitment, performance)

This creates a LIVING relationship profile that evolves with every touchpoint.

Reports to: Relation Building Agent (for persona updates) + Flash (interaction signals)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from enum import Enum

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import ConversationEvent
from app.services.candidate_memory_service import upsert_fact

logger = logging.getLogger(__name__)

class InteractionType(str, Enum):
    """Types of interactions to track"""
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    WHATSAPP_SENT = "whatsapp_sent"
    WHATSAPP_RECEIVED = "whatsapp_received"
    SMS_SENT = "sms_sent"
    SMS_RECEIVED = "sms_received"
    AI_RECRUITER_CONVERSATION = "ai_recruiter_conversation"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    INTERVIEW_FEEDBACK = "interview_feedback"
    OFFER_SENT = "offer_sent"
    OFFER_RESPONSE = "offer_response"
    JOINING_ACCEPTED = "joining_accepted"
    ONBOARDING_STARTED = "onboarding_started"
    DOCUMENT_SUBMITTED = "document_submitted"
    BACKGROUND_CHECK_PASSED = "background_check_passed"

class SentimentScore(str, Enum):
    """Sentiment analysis of interactions"""
    VERY_POSITIVE = "very_positive"  # 1.0
    POSITIVE = "positive"              # 0.75
    NEUTRAL = "neutral"                # 0.5
    NEGATIVE = "negative"              # 0.25
    VERY_NEGATIVE = "very_negative"   # 0.0

class InteractionTracker:
    """
    Tracks all candidate interactions and updates persona continuously.

    Every interaction is:
    1. Captured with metadata (type, channel, timing, sentiment)
    2. Analyzed for relationship signals
    3. Used to update candidate persona
    4. Stored in memory for retrieval
    5. Reported to Flash for coordination
    """

    @staticmethod
    async def track_email_interaction(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        email_text: str,
        direction: str,  # "sent" or "received"
        subject: str = "",
        sent_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Track email interaction and extract relationship signals.

        Analyzes:
        - Response time (if reply)
        - Tone and sentiment
        - Questions asked (engagement indicator)
        - Objections raised (concerns)
        - Call-to-action response
        """
        try:
            # 1. EXTRACT EMAIL SIGNALS
            sentiment = InteractionTracker._analyze_email_sentiment(email_text)
            engagement_level = InteractionTracker._calculate_engagement_level(email_text)
            has_questions = InteractionTracker._detect_questions(email_text)
            has_objections = InteractionTracker._detect_objections(email_text)
            urgency_tone = InteractionTracker._detect_urgency(email_text)

            # 2. CALCULATE RESPONSE TIMING (if this is a reply)
            response_time_hours = None
            if direction == "received":
                # Will be calculated by caller with timestamp comparison
                pass

            # 3. STORE INTERACTION SIGNALS IN MEMORY
            signals_stored = 0

            # Email sentiment
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key=f"email_sentiment_{direction}",
                fact_value=sentiment.value,
                confidence=0.8,
            )
            signals_stored += 1

            # Engagement level from email
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key=f"email_engagement_{direction}",
                fact_value=str(engagement_level),
                confidence=0.75,
            )
            signals_stored += 1

            # Questions asked = genuine interest
            if has_questions and direction == "received":
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="MOTIVATOR",
                    fact_key="engagement_questions_asked",
                    fact_value="true",
                    confidence=0.85,
                )
                signals_stored += 1

            # Objections raised = concerns to address
            if has_objections and direction == "received":
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="OBJECTION",
                    fact_key="email_objection_raised",
                    fact_value="true",
                    confidence=0.8,
                )
                signals_stored += 1

            # Urgency/enthusiasm
            if urgency_tone:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="urgency_signal",
                    fact_value="true",
                    confidence=0.7,
                )
                signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "email",
                "direction": direction,
                "sentiment": sentiment.value,
                "engagement_level": engagement_level,
                "signals_extracted": {
                    "has_questions": has_questions,
                    "has_objections": has_objections,
                    "urgent_tone": urgency_tone,
                },
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Email interaction tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def track_whatsapp_interaction(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        message_text: str,
        direction: str,  # "sent" or "received"
        response_time_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Track WhatsApp/SMS interaction and extract relationship signals.

        Analyzes:
        - Response speed (immediate = high engagement)
        - Message tone (emojis, enthusiasm)
        - Message length (short/dismissive vs engaged)
        - Question engagement
        """
        try:
            # WhatsApp/SMS specific signals
            sentiment = InteractionTracker._analyze_message_sentiment(message_text)
            response_speed = InteractionTracker._calculate_response_speed(response_time_seconds)
            has_emojis = "🎯✅💼🚀" in message_text or any(ord(char) > 127 for char in message_text)
            message_length = len(message_text.split())
            is_enthusiastic = message_length > 20 and any(
                word in message_text.lower() for word in ["excited", "interested", "great", "love", "perfect"]
            )

            # Store signals
            signals_stored = 0

            # Response speed (immediate = high engagement)
            if direction == "received" and response_time_seconds:
                if response_time_seconds < 300:  # 5 minutes = immediate
                    engagement_signal = "immediate"
                    confidence = 0.9
                elif response_time_seconds < 3600:  # 1 hour = engaged
                    engagement_signal = "engaged"
                    confidence = 0.8
                elif response_time_seconds < 86400:  # 1 day = normal
                    engagement_signal = "normal"
                    confidence = 0.7
                else:  # Slow = low priority
                    engagement_signal = "low_priority"
                    confidence = 0.75

                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="whatsapp_response_speed",
                    fact_value=engagement_signal,
                    confidence=confidence,
                )
                signals_stored += 1

            # Sentiment
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key=f"whatsapp_sentiment_{direction}",
                fact_value=sentiment.value,
                confidence=0.8,
            )
            signals_stored += 1

            # Enthusiasm indicators
            if is_enthusiastic and direction == "received":
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="MOTIVATOR",
                    fact_key="whatsapp_enthusiasm",
                    fact_value="true",
                    confidence=0.8,
                )
                signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "whatsapp",
                "direction": direction,
                "sentiment": sentiment.value,
                "response_speed": response_speed,
                "signals_extracted": {
                    "has_emojis": has_emojis,
                    "is_enthusiastic": is_enthusiastic,
                    "message_length": message_length,
                },
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"WhatsApp interaction tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def track_ai_recruiter_conversation(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        conversation_text: str,
        conversation_data: Dict[str, Any],  # Q&A pairs, scores, etc.
    ) -> Dict[str, Any]:
        """
        Track AI Recruiter conversation (Thunder intake).

        Analyzes:
        - Stated preferences (vs resume)
        - Interest level and enthusiasm
        - Objections raised
        - Specific constraints revealed
        - Skill assessments
        - Cultural fit signals
        """
        try:
            # Extract conversation signals
            stated_motivators = InteractionTracker._extract_motivators_from_conversation(
                conversation_text, conversation_data
            )
            revealed_constraints = InteractionTracker._extract_constraints_from_conversation(
                conversation_text, conversation_data
            )
            interest_level = InteractionTracker._calculate_interest_level(conversation_data)
            engagement_quality = InteractionTracker._assess_conversation_engagement(conversation_text)

            signals_stored = 0

            # Update motivators from conversation (may differ from resume)
            for motivator in stated_motivators:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="MOTIVATOR",
                    fact_key=f"stated_{motivator}",
                    fact_value="true",
                    confidence=0.85,  # Higher confidence: stated directly
                )
                signals_stored += 1

            # Revealed constraints
            for constraint in revealed_constraints:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="CONSTRAINT",
                    fact_key=f"revealed_{constraint}",
                    fact_value="true",
                    confidence=0.9,  # Very high: stated in conversation
                )
                signals_stored += 1

            # Interest level (updated from conversation)
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="conversation_interest_level",
                fact_value=str(interest_level),
                confidence=0.85,
            )
            signals_stored += 1

            # Engagement quality
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="conversation_engagement_quality",
                fact_value=engagement_quality,
                confidence=0.8,
            )
            signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "ai_recruiter_conversation",
                "interest_level": interest_level,
                "engagement_quality": engagement_quality,
                "stated_motivators": stated_motivators,
                "revealed_constraints": revealed_constraints,
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"AI Recruiter conversation tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def track_interview_feedback(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        interview_data: Dict[str, Any],  # feedback, scores, panel comments
    ) -> Dict[str, Any]:
        """
        Track interview feedback and update relationship profile.

        Analyzes:
        - Panel enthusiasm and recommendation
        - Technical/soft skill assessment
        - Cultural fit assessment
        - Candidate enthusiasm during interview
        - Interview no-show/reschedule patterns
        """
        try:
            panel_score = interview_data.get("overall_score", 0)  # 1-10
            panel_recommendation = interview_data.get("recommendation", "")  # hire/strong/maybe/no
            panel_feedback = interview_data.get("feedback", "")
            candidate_enthusiasm = InteractionTracker._assess_interview_enthusiasm(panel_feedback)
            cultural_fit = interview_data.get("cultural_fit_score", 5)  # 1-10

            signals_stored = 0

            # Panel recommendation (strong signal)
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="panel_recommendation",
                fact_value=panel_recommendation,
                confidence=0.95,  # Very high: from hiring team
            )
            signals_stored += 1

            # Panel score
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="interview_panel_score",
                fact_value=str(panel_score),
                confidence=0.9,
            )
            signals_stored += 1

            # Candidate enthusiasm during interview
            if candidate_enthusiasm:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="interview_enthusiasm",
                    fact_value=candidate_enthusiasm,
                    confidence=0.85,
                )
                signals_stored += 1

            # Cultural fit
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="cultural_fit_score",
                fact_value=str(cultural_fit),
                confidence=0.85,
            )
            signals_stored += 1

            # Update engagement readiness based on interview performance
            if panel_score >= 8:
                engagement_update = "very_high"
            elif panel_score >= 6:
                engagement_update = "high"
            else:
                engagement_update = "medium"

            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="engagement_readiness_post_interview",
                fact_value=engagement_update,
                confidence=0.9,
            )
            signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "interview_feedback",
                "panel_score": panel_score,
                "panel_recommendation": panel_recommendation,
                "candidate_enthusiasm": candidate_enthusiasm,
                "cultural_fit": cultural_fit,
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Interview feedback tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def track_offer_response(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        offer_response_data: Dict[str, Any],  # response_time, negotiation, acceptance
    ) -> Dict[str, Any]:
        """
        Track offer response and update relationship profile.

        Analyzes:
        - Speed of response (fast = eager, slow = considering)
        - Negotiation signals (wants more = has options)
        - Questions about offer (engagement)
        - Acceptance/rejection (final signal)
        - Stated reasons for acceptance/rejection
        """
        try:
            response_time_hours = offer_response_data.get("response_time_hours", 0)
            is_accepting = offer_response_data.get("is_accepting", False)
            negotiation_requested = offer_response_data.get("negotiation_requested", False)
            questions_asked = offer_response_data.get("questions_asked", [])
            response_tone = offer_response_data.get("response_tone", "neutral")  # excited/hesitant/neutral

            signals_stored = 0

            # Response speed (quick acceptance = high commitment)
            if response_time_hours <= 24 and is_accepting:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="offer_acceptance_speed",
                    fact_value="immediate",
                    confidence=0.95,
                )
                signals_stored += 1

            # Negotiation signals
            if negotiation_requested:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="CONSTRAINT",
                    fact_key="negotiation_difficulty",
                    fact_value="true",
                    confidence=0.9,
                )
                signals_stored += 1

            # Tone of response
            if response_tone == "excited" and is_accepting:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="offer_acceptance_enthusiasm",
                    fact_value="high",
                    confidence=0.9,
                )
                signals_stored += 1

            # Final decision
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="offer_decision",
                fact_value="accepted" if is_accepting else "rejected",
                confidence=1.0,
            )
            signals_stored += 1

            # Update engagement readiness based on offer response
            if is_accepting:
                engagement_update = "very_high"
            else:
                engagement_update = "low"

            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="engagement_readiness_post_offer",
                fact_value=engagement_update,
                confidence=0.95,
            )
            signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "offer_response",
                "is_accepting": is_accepting,
                "response_speed": "immediate" if response_time_hours <= 24 else "slow",
                "negotiation_requested": negotiation_requested,
                "offer_enthusiasm": response_tone,
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Offer response tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def track_joining_signals(
        candidate_id: str,
        tenant_id: str,
        db: Session,
        joining_data: Dict[str, Any],  # document submission, onboarding progress
    ) -> Dict[str, Any]:
        """
        Track joining signals and long-term commitment indicators.

        Analyzes:
        - Document submission speed
        - Background check passage
        - Onboarding engagement
        - First-week performance signals
        - Early attrition indicators
        """
        try:
            document_submission_speed = joining_data.get("document_submission_speed", "slow")
            background_check_passed = joining_data.get("background_check_passed", True)
            onboarding_engagement = joining_data.get("onboarding_engagement", "normal")
            early_performance = joining_data.get("early_performance_signals", {})

            signals_stored = 0

            # Document submission speed
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="joining_document_speed",
                fact_value=document_submission_speed,
                confidence=0.85,
            )
            signals_stored += 1

            # Background check
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="background_check_status",
                fact_value="passed" if background_check_passed else "failed",
                confidence=1.0,
            )
            signals_stored += 1

            # Onboarding engagement
            upsert_fact(
                db, candidate_id, tenant_id,
                fact_category="PERSONAL",
                fact_key="onboarding_engagement",
                fact_value=onboarding_engagement,
                confidence=0.8,
            )
            signals_stored += 1

            # Early performance signals (if available)
            if "attrition_risk" in early_performance:
                upsert_fact(
                    db, candidate_id, tenant_id,
                    fact_category="PERSONAL",
                    fact_key="early_attrition_risk",
                    fact_value=str(early_performance["attrition_risk"]),
                    confidence=0.7,
                )
                signals_stored += 1

            db.commit()

            return {
                "status": "success",
                "interaction_type": "joining_signals",
                "document_speed": document_submission_speed,
                "background_check": "passed" if background_check_passed else "failed",
                "onboarding_engagement": onboarding_engagement,
                "signals_stored": signals_stored,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Joining signals tracking error: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ============== HELPER METHODS ==============

    @staticmethod
    def _analyze_email_sentiment(text: str) -> SentimentScore:
        """Analyze email sentiment from text."""
        positive_words = ["great", "excited", "interested", "perfect", "love", "excellent", "enthusiastic"]
        negative_words = ["concerned", "worried", "hesitant", "confused", "unclear", "problem"]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count + 2:
            return SentimentScore.VERY_POSITIVE
        elif positive_count > negative_count:
            return SentimentScore.POSITIVE
        elif negative_count > positive_count + 2:
            return SentimentScore.VERY_NEGATIVE
        elif negative_count > positive_count:
            return SentimentScore.NEGATIVE
        else:
            return SentimentScore.NEUTRAL

    @staticmethod
    def _calculate_engagement_level(text: str) -> float:
        """Calculate engagement level from email content (0.0 to 1.0)."""
        # Longer, more detailed emails = higher engagement
        word_count = len(text.split())
        question_count = text.count("?")
        exclamation_count = text.count("!")

        # Base score from length
        if word_count < 50:
            score = 0.3
        elif word_count < 200:
            score = 0.6
        else:
            score = 0.9

        # Boost for questions and enthusiasm
        score += (question_count * 0.1)
        score += (exclamation_count * 0.05)

        return min(1.0, score)

    @staticmethod
    def _detect_questions(text: str) -> bool:
        """Detect if email contains questions."""
        return "?" in text

    @staticmethod
    def _detect_objections(text: str) -> bool:
        """Detect if email raises objections/concerns."""
        objection_words = ["but", "however", "concerned", "worry", "problem", "issue", "hesitant", "unsure"]
        return any(word in text.lower() for word in objection_words)

    @staticmethod
    def _detect_urgency(text: str) -> bool:
        """Detect urgency/enthusiasm tone."""
        urgency_words = ["asap", "urgent", "immediately", "excited", "looking forward", "can't wait"]
        return any(word in text.lower() for word in urgency_words)

    @staticmethod
    def _analyze_message_sentiment(text: str) -> SentimentScore:
        """Analyze WhatsApp/SMS message sentiment."""
        return InteractionTracker._analyze_email_sentiment(text)

    @staticmethod
    def _calculate_response_speed(response_seconds: Optional[int]) -> str:
        """Categorize response speed."""
        if not response_seconds:
            return "unknown"
        if response_seconds < 300:  # 5 min
            return "immediate"
        elif response_seconds < 3600:  # 1 hour
            return "quick"
        elif response_seconds < 86400:  # 1 day
            return "normal"
        else:
            return "slow"

    @staticmethod
    def _extract_motivators_from_conversation(text: str, data: Dict) -> List[str]:
        """Extract stated motivators from AI Recruiter conversation."""
        motivators = []
        text_lower = text.lower()

        if any(w in text_lower for w in ["grow", "learn", "develop", "advance"]):
            motivators.append("growth")
        if any(w in text_lower for w in ["stable", "established", "benefits", "remote"]):
            motivators.append("stability")
        if any(w in text_lower for w in ["salary", "compensation", "market"]):
            motivators.append("compensation")
        if any(w in text_lower for w in ["impact", "mission", "meaningful"]):
            motivators.append("impact")
        if any(w in text_lower for w in ["lead", "manage", "team"]):
            motivators.append("leadership")

        return motivators

    @staticmethod
    def _extract_constraints_from_conversation(text: str, data: Dict) -> List[str]:
        """Extract revealed constraints from AI Recruiter conversation."""
        constraints = []
        text_lower = text.lower()

        if any(w in text_lower for w in ["local", "relocation", "remote"]):
            constraints.append("geographic_constraint")
        if any(w in text_lower for w in ["within", "weeks", "notice"]):
            constraints.append("availability_window")
        if any(w in text_lower for w in ["must have", "requirement"]):
            constraints.append("hard_requirement")

        return constraints

    @staticmethod
    def _calculate_interest_level(conversation_data: Dict) -> float:
        """Calculate interest level from conversation (0.0 to 1.0)."""
        score = 0.5  # Start neutral

        # Higher score if asking many questions
        if conversation_data.get("questions_asked", 0) > 3:
            score += 0.3

        # Higher score if willing to continue
        if conversation_data.get("willing_to_continue", False):
            score += 0.2

        return min(1.0, score)

    @staticmethod
    def _assess_conversation_engagement(text: str) -> str:
        """Assess engagement quality in conversation."""
        word_count = len(text.split())
        if word_count > 500:
            return "high"
        elif word_count > 200:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _assess_interview_enthusiasm(feedback: str) -> str:
        """Assess candidate enthusiasm from interview feedback."""
        positive_feedback = ["enthusiastic", "engaged", "interested", "passionate", "eager"]
        if any(word in feedback.lower() for word in positive_feedback):
            return "high"
        elif "interested" in feedback.lower():
            return "medium"
        else:
            return "low"
