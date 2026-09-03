"""SLM (Small Language Model) Service - Analyzes message results and decides next actions

After each message processes, SLM analyzes the result and determines the next action for Flash agent.
Examples:
- "Candidate added" → SLM → "Thunder should email candidate"
- "Thunder failed to email" → SLM → "Escalate to Flash for manual contact"
- "Interview scheduled" → SLM → "Next: offer generation workflow"

Implements FAIL FAST: All methods raise exceptions on error.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)


class SLMService:
    """Service for SLM analysis and decision making with fail-fast error handling."""

    # Decision types
    DECISION_ESCALATE = "escalate"
    DECISION_NEXT_ACTION = "next_action"
    DECISION_MANUAL_REVIEW = "manual_review"
    DECISION_AUTO_PROCEED = "auto_proceed"

    # Next action types
    ACTION_SEND_EMAIL = "send_email"
    ACTION_SCHEDULE_INTERVIEW = "schedule_interview"
    ACTION_GENERATE_OFFER = "generate_offer"
    ACTION_ESCALATE_TO_MANAGER = "escalate_to_manager"
    ACTION_TRY_NEXT_CANDIDATE = "try_next_candidate"
    ACTION_NONE = "none"

    @staticmethod
    def analyze_message_result(
        message_id: str,
        message_type: str,
        result: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Analyze message processing result and return decision.

        Args:
            message_id: ID of message being analyzed
            message_type: Type of message (e.g., 'candidate_added', 'thunder_email_sent')
            result: Result dict from message processing
            db: Database session

        Returns:
            Decision dict with decision_type, next_action, confidence_score, etc.

        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If analysis fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            if not message_id or not message_type:
                raise ValueError("message_id and message_type required")

            # Route to type-specific analyzer
            if message_type == "candidate_added":
                decision = SLMService._analyze_candidate_added(result)
            elif message_type == "thunder_email_sent":
                decision = SLMService._analyze_thunder_email_sent(result)
            elif message_type == "flash_agent_action":
                decision = SLMService._analyze_flash_action(result)
            elif message_type == "interview_scheduled":
                decision = SLMService._analyze_interview_scheduled(result)
            elif message_type == "offer_generated":
                decision = SLMService._analyze_offer_generated(result)
            else:
                # Default: log and proceed
                logger.warning(f"Unknown message type: {message_type}")
                decision = {
                    "decision_type": SLMService.DECISION_AUTO_PROCEED,
                    "next_action": SLMService.ACTION_NONE,
                    "confidence_score": 0.5,
                    "reason": f"Unknown message type: {message_type}",
                }

            # Store decision
            SLMService._store_decision(message_id, decision, db)

            logger.info(
                f"SLM analysis complete: message_id={message_id} "
                f"decision={decision['decision_type']} "
                f"next_action={decision['next_action']} "
                f"confidence={decision['confidence_score']}"
            )

            return decision

        except Exception as e:
            logger.error(f"Failed to analyze message result: {e}", exc_info=True)
            raise RuntimeError(f"Failed to analyze message result: {str(e)}")

    @staticmethod
    def _analyze_candidate_added(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze candidate_added message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.9,
                "reason": "Candidate creation failed",
                "details": result.get("error"),
            }

        # Candidate added successfully → Thunder should contact them
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_SEND_EMAIL,
            "confidence_score": 0.95,
            "reason": "New candidate should be contacted by Thunder",
            "details": {"target": "send_candidate_welcome_email"},
        }

    @staticmethod
    def _analyze_thunder_email_sent(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze thunder_email_sent message."""
        success = result.get("success", False)
        retries = result.get("retry_count", 0)

        if not success:
            if retries >= 3:
                return {
                    "decision_type": SLMService.DECISION_ESCALATE,
                    "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                    "confidence_score": 0.85,
                    "reason": "Thunder email failed after multiple retries",
                    "details": result.get("error"),
                }
            else:
                return {
                    "decision_type": SLMService.DECISION_AUTO_PROCEED,
                    "next_action": SLMService.ACTION_SEND_EMAIL,
                    "confidence_score": 0.6,
                    "reason": "Retry Thunder email delivery",
                }

        # Email sent successfully → Wait for engagement
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.9,
            "reason": "Thunder email sent, monitoring engagement",
        }

    @staticmethod
    def _analyze_flash_action(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze flash_agent_action message."""
        action_type = result.get("action_type")
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.85,
                "reason": f"Flash action failed: {action_type}",
                "details": result.get("error"),
            }

        # Determine next action based on what Flash did
        if action_type == "schedule_interview":
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.95,
                "reason": "Interview scheduled, waiting for completion",
            }

        elif action_type == "generate_offer":
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.9,
                "reason": "Offer generated, pending approval",
            }

        else:
            return {
                "decision_type": SLMService.DECISION_AUTO_PROCEED,
                "next_action": SLMService.ACTION_NONE,
                "confidence_score": 0.7,
                "reason": f"Flash action completed: {action_type}",
            }

    @staticmethod
    def _analyze_interview_scheduled(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze interview_scheduled message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.8,
                "reason": "Failed to schedule interview",
                "details": result.get("error"),
            }

        # Interview scheduled → Notify panel
        return {
            "decision_type": SLMService.DECISION_AUTO_PROCEED,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.95,
            "reason": "Interview scheduled, panel notifications sent",
        }

    @staticmethod
    def _analyze_offer_generated(result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze offer_generated message."""
        success = result.get("success", False)

        if not success:
            return {
                "decision_type": SLMService.DECISION_MANUAL_REVIEW,
                "next_action": SLMService.ACTION_ESCALATE_TO_MANAGER,
                "confidence_score": 0.8,
                "reason": "Failed to generate offer",
                "details": result.get("error"),
            }

        # Offer generated → Manager approval
        return {
            "decision_type": SLMService.DECISION_MANUAL_REVIEW,
            "next_action": SLMService.ACTION_NONE,
            "confidence_score": 0.9,
            "reason": "Offer generated, awaiting manager approval",
        }

    @staticmethod
    def _store_decision(
        message_id: str,
        decision: Dict[str, Any],
        db: Session,
    ) -> str:
        """
        Store SLM decision in database.

        Args:
            message_id: Message ID
            decision: Decision dict
            db: Database session

        Returns:
            Decision ID

        Raises:
            RuntimeError: If storage fails
        """
        try:
            from app.models.slm_decision import SLMDecision

            decision_id = str(uuid.uuid4())
            decision_record = SLMDecision(
                id=decision_id,
                message_id=message_id,
                decision_type=decision.get("decision_type", SLMService.DECISION_AUTO_PROCEED),
                decision_details=decision,
                confidence_score=decision.get("confidence_score", 0.5),
                next_action=decision.get("next_action", SLMService.ACTION_NONE),
            )

            db.add(decision_record)
            db.commit()

            logger.debug(f"SLM decision stored: {decision_id} for message: {message_id}")
            return decision_id

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Failed to store SLM decision: {e}", exc_info=True)
            raise RuntimeError(f"Failed to store SLM decision: {str(e)}")
