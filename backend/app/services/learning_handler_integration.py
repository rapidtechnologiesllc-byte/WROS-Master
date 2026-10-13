"""Learning Handler Integration - Wires learning into message handlers

Every message handler (Thunder, Flash, Interview, Offer, Finance) needs to:
1. Make a DECISION with predicted outcome
2. Record that decision with confidence score
3. Later, when outcome is known, record actual result
4. Learning system updates weights based on accuracy

This module provides decorator and utility functions to make integration easy.
"""

import logging
import uuid
from datetime import datetime
from typing import Callable, Any, Dict, Optional
from functools import wraps
from sqlalchemy.orm import Session

from app.services.learning_outcome_tracker import (
    LearningOutcomeTracker,
    DecisionOutcome,
)

logger = logging.getLogger(__name__)


def track_decision(
    orchestrator: str,
    decision_type: str,
    predicted_outcome: str,
    confidence_key: Optional[str] = None,  # JSON path if confidence is in result
):
    """
    Decorator to automatically track decisions made by handlers.

    Usage:
        @track_decision(
            orchestrator="thunder",
            decision_type="email_sent",
            predicted_outcome="engagement",
            confidence_key="confidence_score"
        )
        def send_email_handler(self, message, db):
            # Handler returns result with confidence_score field
            return {"success": True, "confidence_score": 0.72, ...}

    The decorator:
    1. Captures predicted outcome and confidence from handler result
    2. Creates decision record
    3. Stores in context for later outcome recording
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, message: Dict[str, Any], db: Session, *args, **kwargs):
            # Call the actual handler
            result = func(self, message, db, *args, **kwargs)

            # Extract confidence if provided
            confidence = 0.5  # Default
            if confidence_key and isinstance(result, dict):
                confidence = result.get(confidence_key, 0.5)

            # Create decision record
            try:
                entity_id = message.get("entity_id") or message.get("candidate_id") or message.get("job_id")
                decision_record = LearningOutcomeTracker.create_decision(
                    db=db,
                    orchestrator=orchestrator,
                    decision_type=decision_type,
                    entity_id=entity_id,
                    predicted_outcome=predicted_outcome,
                    predicted_probability=confidence,
                    decision_metadata={
                        "handler": func.__name__,
                        "message_type": message.get("type"),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                # Store decision_id in result for later outcome recording
                if isinstance(result, dict):
                    result["_learning_decision_id"] = decision_record["decision_id"]
                    result["_learning_decision"] = decision_record["decision"]

                logger.info(
                    f"[LearningIntegration] Tracked {decision_type} decision: "
                    f"id={decision_record['decision_id']} "
                    f"confidence={confidence:.2f}"
                )

            except Exception as e:
                logger.error(
                    f"[LearningIntegration] Failed to track decision in {func.__name__}: {e}"
                )
                # Don't fail the handler, just skip tracking

            return result

        return wrapper

    return decorator


def record_outcome(
    decision_id_key: str = "_learning_decision_id",
    decision_obj_key: str = "_learning_decision",
    outcome_key: str = "outcome",
    success_key: str = "success",
):
    """
    Decorator to record actual outcome when it becomes available.

    Usage (called later, when result is known):
        @record_outcome(
            decision_id_key="_learning_decision_id",
            outcome_key="actual_outcome",
            success_key="result_success"
        )
        def record_email_engagement(self, handler_result, outcome_result, db):
            # outcome_result = actual email open/click
            # handler_result = original decision with _learning_decision_id
            return {...}

    This is called when we learn the actual result (e.g., email opened 2h later)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(
            self,
            handler_result: Dict[str, Any],
            outcome_result: Dict[str, Any],
            db: Session,
            *args,
            **kwargs
        ):
            # Call the actual recording function
            result = func(self, handler_result, outcome_result, db, *args, **kwargs)

            # Extract decision info
            decision_id = handler_result.get(decision_id_key)
            decision = handler_result.get(decision_obj_key)

            if decision and decision_id:
                try:
                    actual_outcome = outcome_result.get(outcome_key, "unknown")
                    actual_success = outcome_result.get(success_key, False)

                    # Record the outcome
                    outcome_record = LearningOutcomeTracker.record_outcome(
                        decision=decision,
                        actual_outcome=actual_outcome,
                        actual_result=actual_success,
                        outcome_metadata={
                            "outcome_details": outcome_result,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

                    logger.info(
                        f"[LearningIntegration] Recorded outcome for decision {decision_id}: "
                        f"predicted={decision.predicted_outcome} "
                        f"actual={actual_outcome} "
                        f"success={actual_success}"
                    )

                except Exception as e:
                    logger.error(
                        f"[LearningIntegration] Failed to record outcome: {e}"
                    )

            return result

        return wrapper

    return decorator


class HandlerLearningMixin:
    """Mixin to add learning capabilities to message handlers"""

    def create_tracked_decision(
        self,
        db: Session,
        orchestrator: str,
        decision_type: str,
        entity_id: str,
        predicted_outcome: str,
        confidence: float,
        metadata: Dict[str, Any],
    ) -> DecisionOutcome:
        """
        Create and track a decision within handler.

        Usage:
            decision = self.create_tracked_decision(
                db=db,
                orchestrator="thunder",
                decision_type="email_sent",
                entity_id=candidate_id,
                predicted_outcome="engagement",
                confidence=0.72,
                metadata={"channel": "email", "template": "tech_intro"}
            )
        """
        record = LearningOutcomeTracker.create_decision(
            db=db,
            orchestrator=orchestrator,
            decision_type=decision_type,
            entity_id=entity_id,
            predicted_outcome=predicted_outcome,
            predicted_probability=confidence,
            decision_metadata=metadata,
        )
        return record["decision"]

    def record_decision_outcome(
        self,
        decision: DecisionOutcome,
        actual_outcome: str,
        success: bool,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Record outcome for a previously tracked decision.

        Usage:
            outcome = self.record_decision_outcome(
                decision=decision,
                actual_outcome="email_opened",
                success=True,
                metadata={"open_time_hours": 2.5}
            )
        """
        return LearningOutcomeTracker.record_outcome(
            decision=decision,
            actual_outcome=actual_outcome,
            actual_result=success,
            outcome_metadata=metadata,
        )

    def should_use_learning_recommendation(
        self,
        recommendation: Dict[str, Any],
        confidence_threshold: float = 0.70,
    ) -> bool:
        """
        Check if a learning recommendation should be used.

        Only apply recommendations with sufficient confidence.
        """
        return recommendation.get("confidence_score", 0.0) >= confidence_threshold


class LearningIntegrationHelper:
    """Helper functions for learning integration in handlers"""

    @staticmethod
    def extract_decision_metadata_from_handler(
        handler_name: str, message: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract metadata about decision from handler context.

        Args:
            handler_name: Name of handler function
            message: Input message
            context: Handler execution context

        Returns:
            Dictionary with decision metadata (factors that influenced decision)
        """
        return {
            "handler": handler_name,
            "message_type": message.get("type"),
            "message_id": message.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
            "context_keys": list(context.keys()) if context else [],
        }

    @staticmethod
    def extract_outcome_metadata_from_event(
        event_name: str, event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract metadata about outcome from event data.

        Args:
            event_name: Name of outcome event (e.g., "email_opened")
            event_data: Event details

        Returns:
            Dictionary with outcome metadata
        """
        return {
            "event": event_name,
            "event_timestamp": event_data.get("timestamp"),
            "event_data": event_data,
        }

    @staticmethod
    def build_confidence_from_factors(
        factors: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Combine multiple factors into single confidence score.

        Args:
            factors: {"factor1": 0.8, "factor2": 0.6, ...}
            weights: {"factor1": 0.6, "factor2": 0.4, ...} (defaults to equal weights)

        Returns:
            Combined confidence score (0.0-1.0)
        """
        if not factors:
            return 0.5

        if weights is None:
            # Equal weights
            weights = {k: 1.0 / len(factors) for k in factors}

        weighted_sum = sum(
            factors.get(k, 0.5) * weights.get(k, 0.0) for k in factors
        )
        return max(0.0, min(1.0, weighted_sum))
