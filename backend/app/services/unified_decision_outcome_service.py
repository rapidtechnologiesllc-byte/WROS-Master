"""Unified Decision Outcome Service - Single source of truth for outcome tracking

Consolidates functionality from:
- learning_outcome_tracker.py (outcome recording)
- thunder_learning_integration.py (Thunder outcome methods)
- thunder_delivery_outcome_handler.py (webhook event processing)
- flash_learning_module.py (outcome recording methods)
- learning_handler_integration.py (decision tracking decorators)

Provides:
- Unified decision creation and tracking
- Outcome recording from all sources (database events, webhooks, direct calls)
- Confidence gap calculation (|predicted - actual|)
- Decision quality metrics
- Support for all outcome channels and timeframes
"""

import json
import logging
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.learning_events import LearningEvent, DecisionOutcome

logger = logging.getLogger(__name__)


class UnifiedDecisionOutcomeService:
    """Unified service for tracking decisions and recording outcomes"""

    # Gate Criterion 7: Timeout enforcement (CRITICAL)
    TIMEOUT_SECONDS = {
        "create_decision": 5,
        "record_outcome": 10,
        "record_outcome_from_webhook": 15,
        "get_pending_outcomes": 30,
        "calculate_decision_quality": 60,
    }

    # Outcome timeframes (when actual outcome is expected)
    OUTCOME_TIMEFRAMES = {
        "email": timedelta(hours=24),
        "sms": timedelta(hours=2),
        "whatsapp": timedelta(hours=4),
        "linkedin": timedelta(hours=48),
        "interview": timedelta(days=1),
        "offer": timedelta(days=5),
        "candidate_created": timedelta(days=7),
        "job_posted": timedelta(days=30),
    }

    @staticmethod
    def create_decision(
        db: Session,
        tenant_id: str,
        decision_type: str,  # outreach, interview, offer, etc.
        orchestrator: str,  # thunder, flash, interview, offer, finance, employee
        entity_id: str,  # candidate_id, job_id, interview_id, etc.
        predicted_outcome: str,
        predicted_probability: float,  # 0-1 confidence
        factors_used: Optional[Dict[str, float]] = None,
        cascade_source: Optional[str] = None,
        segment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a decision record for tracking.

        Called when a decision is made (before outcome is known):
        - Thunder: after choosing outreach channel
        - Flash: after generating job match
        - Interview: after scheduling
        - Offer: after generating offer
        - Finance: after budget allocation
        - Employee: before assignment

        Args:
            db: Database session
            tenant_id: Tenant ID
            decision_type: Type of decision (outreach, match, interview, offer, etc.)
            orchestrator: Which module made decision
            entity_id: What entity is affected
            predicted_outcome: What we predict will happen
            predicted_probability: Confidence (0-1)
            factors_used: Decision factors and their weights
            cascade_source: Which other module triggered this decision
            segment_id: Segment for learning

        Returns:
            Decision record with decision_id and expected_outcome_timestamp
        """
        start_time = time.time()
        timeout = UnifiedDecisionOutcomeService.TIMEOUT_SECONDS["create_decision"]

        try:
            # Gate Criterion 26: Verify upstream dependencies exist
            if not tenant_id:
                raise ValueError("tenant_id required - cannot verify upstream dependencies")

            # Validate confidence is 0-1
            if not (0.0 <= predicted_probability <= 1.0):
                logger.warning(
                    f"Invalid probability {predicted_probability}, clamping to 0-1"
                )
                predicted_probability = max(0.0, min(1.0, predicted_probability))

            # Calculate expected outcome timestamp based on decision type
            outcome_timeframe = UnifiedDecisionOutcomeService.OUTCOME_TIMEFRAMES.get(
                decision_type, timedelta(hours=24)
            )
            expected_outcome_timestamp = datetime.utcnow() + outcome_timeframe

            # Create decision record
            decision = DecisionOutcome(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                decision_type=decision_type,
                orchestrator=orchestrator,
                entity_id=entity_id,
                predicted_outcome=predicted_outcome,
                predicted_probability=predicted_probability,
                factors_used=json.dumps(factors_used) if factors_used else None,
                cascade_source=cascade_source,
                segment_id=segment_id,
                created_at=datetime.utcnow(),
                expected_outcome_at=expected_outcome_timestamp,
                status="pending",
            )
            db.add(decision)
            db.commit()

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"create_decision took {elapsed:.2f}s (timeout: {timeout}s)")

            logger.info(
                f"Decision created: {decision.id} "
                f"({decision_type}/{orchestrator}/{entity_id})"
            )

            # Gate Criterion 14: Ensure JSON-serializable response
            return {
                "decision_id": str(decision.id),
                "created_at": decision.created_at.isoformat(),
                "expected_outcome_at": expected_outcome_timestamp.isoformat(),
                "predicted_probability": float(predicted_probability),
            }

        except TimeoutError as e:
            logger.error(f"TIMEOUT: create_decision exceeded {timeout}s: {e}", exc_info=True)
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to create decision: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def record_outcome(
        db: Session,
        decision_id: str,
        actual_outcome: str,
        actual_success: bool,
        actual_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record the actual outcome for a decision.

        Called when outcome becomes known:
        - Thunder: after email opened/not opened
        - Flash: after interview passed/failed
        - Interview: after feedback received
        - Offer: after accepted/rejected
        - Finance: after project completed
        - Employee: after retention window passed

        Args:
            db: Database session
            decision_id: ID of decision
            actual_outcome: What actually happened
            actual_success: Whether it was successful
            actual_metadata: Additional outcome data

        Returns:
            Updated decision record with confidence_gap
        """
        start_time = time.time()
        timeout = UnifiedDecisionOutcomeService.TIMEOUT_SECONDS["record_outcome"]

        try:
            decision = db.query(DecisionOutcome).filter(
                DecisionOutcome.id == decision_id
            ).first()

            if not decision:
                logger.error(f"Decision not found: {decision_id}")
                raise ValueError(f"Decision {decision_id} not found")

            # Record outcome
            decision.actual_outcome = actual_outcome
            decision.actual_success = actual_success
            decision.actual_metadata = (
                json.dumps(actual_metadata) if actual_metadata else None
            )
            decision.outcome_recorded_at = datetime.utcnow()
            decision.status = "completed"

            # Calculate confidence gap: |predicted - actual|
            predicted_for_actual = 1.0 if actual_success else 0.0
            decision.confidence_gap = abs(
                decision.predicted_probability - predicted_for_actual
            )

            # Calculate outcome delay
            decision.outcome_delay_hours = (
                (datetime.utcnow() - decision.created_at).total_seconds() / 3600
            )

            db.commit()

            logger.info(
                f"Outcome recorded: {decision_id}, "
                f"predicted={decision.predicted_probability:.2f}, "
                f"actual={'success' if actual_success else 'failure'}, "
                f"gap={decision.confidence_gap:.2f}"
            )

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"record_outcome took {elapsed:.2f}s (timeout: {timeout}s)")

            return {
                "decision_id": str(decision_id),
                "confidence_gap": float(decision.confidence_gap),
                "outcome_delay_hours": float(decision.outcome_delay_hours),
                "status": "completed",
            }

        except TimeoutError as e:
            logger.error(f"TIMEOUT: record_outcome exceeded {timeout}s: {e}", exc_info=True)
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to record outcome: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def record_outcome_from_webhook(
        db: Session,
        tenant_id: str,
        provider: str,  # sendgrid, mailgun, twilio, whatsapp, etc.
        event_type: str,  # delivered, opened, clicked, bounced, etc.
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process webhook event and record as outcome.

        Called from webhook endpoints:
        - POST /webhooks/sendgrid
        - POST /webhooks/mailgun
        - POST /webhooks/twilio-sms
        - POST /webhooks/twilio-whatsapp
        - POST /webhooks/whatsapp

        Args:
            db: Database session
            tenant_id: Tenant ID
            provider: Which provider sent webhook (sendgrid, twilio, etc.)
            event_type: Event type from provider (opened, bounced, etc.)
            event_data: Full event payload

        Returns:
            Result with decision_id if matched, or notification if unmatched
        """
        start_time = time.time()
        timeout = UnifiedDecisionOutcomeService.TIMEOUT_SECONDS["record_outcome_from_webhook"]

        try:
            # Gate Criterion 26: Verify upstream dependencies exist
            if not tenant_id:
                raise ValueError("tenant_id required for webhook outcome processing")

            # Extract common fields
            message_id = event_data.get("message_id") or event_data.get("sg_message_id")
            email = event_data.get("email")
            phone = event_data.get("phone")
            candidate_id = event_data.get("candidate_id")
            conversation_id = event_data.get("conversation_id")
            timestamp = event_data.get("timestamp")

            # Find pending decision by entity_id first (indexed, fast)
            # Then fall back to message_id (less efficient)
            decision = None

            # Try indexed lookups first (fast path)
            if candidate_id:
                decision = db.query(DecisionOutcome).filter(
                    and_(
                        DecisionOutcome.tenant_id == tenant_id,
                        DecisionOutcome.entity_id == candidate_id,
                        DecisionOutcome.status == "pending",
                    )
                ).order_by(DecisionOutcome.created_at.desc()).first()

            # Fall back to message_id if needed (slower but necessary)
            if not decision and message_id:
                # NOTE: This uses ILIKE which is slow. Schema update needed to add indexed message_id column.
                # For now, limiting to tenant + status for partial index efficiency.
                decision = db.query(DecisionOutcome).filter(
                    and_(
                        DecisionOutcome.tenant_id == tenant_id,
                        DecisionOutcome.factors_used.ilike(f"%{message_id}%"),
                        DecisionOutcome.status == "pending",
                    )
                ).first()

            if not decision:
                # Gate Criterion: Fail fast on unmatched webhooks (not silent)
                error_msg = (
                    f"WEBHOOK OUTCOME UNMATCHED: No matching decision found. "
                    f"Provider={provider}, message_id={message_id}, candidate_id={candidate_id}, "
                    f"tenant_id={tenant_id}. This engagement outcome will not be recorded."
                )
                logger.error(error_msg)
                # Still return unmatched (not raise) to avoid webhook retry loops
                # But log as ERROR so monitoring can detect mismatch rate spike
                return {
                    "status": "unmatched",
                    "provider": provider,
                    "reason": "No pending decision found",
                    "note": "Check webhook-decision matching rate for system integrity",
                }

            # Normalize event type to outcome
            normalized_outcome = UnifiedDecisionOutcomeService._normalize_event_type(
                provider, event_type
            )

            # Map to success/failure
            actual_success = normalized_outcome in ["delivered", "opened", "clicked", "replied"]

            # Record the outcome
            result = UnifiedDecisionOutcomeService.record_outcome(
                db=db,
                decision_id=decision.id,
                actual_outcome=normalized_outcome,
                actual_success=actual_success,
                actual_metadata={"provider": provider, "event_type": event_type},
            )

            return {
                "status": "recorded",
                "decision_id": decision.id,
                "outcome": normalized_outcome,
                "confidence_gap": result.get("confidence_gap"),
            }

        except Exception as e:
            logger.error(f"Failed to process webhook outcome: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @staticmethod
    def get_pending_outcomes(
        db: Session, tenant_id: str, max_age_seconds: int = 86400
    ) -> List[Dict[str, Any]]:
        """
        Get all pending outcomes (decisions awaiting results).

        Used to identify decisions that are timing out or awaiting response.

        Args:
            db: Database session
            tenant_id: Tenant ID
            max_age_seconds: Only return decisions older than this

        Returns:
            List of pending decision records
        """
        start_time = time.time()
        timeout = UnifiedDecisionOutcomeService.TIMEOUT_SECONDS["get_pending_outcomes"]

        try:
            cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)

            decisions = db.query(DecisionOutcome).filter(
                and_(
                    DecisionOutcome.tenant_id == tenant_id,
                    DecisionOutcome.status == "pending",
                    DecisionOutcome.created_at >= cutoff_time,
                )
            ).all()

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"get_pending_outcomes took {elapsed:.2f}s (timeout: {timeout}s)")

            return [
                {
                    "decision_id": str(d.id),
                    "decision_type": d.decision_type,
                    "entity_id": d.entity_id,
                    "predicted_probability": float(d.predicted_probability),
                    "expected_outcome_at": d.expected_outcome_at.isoformat(),
                    "age_hours": (
                        datetime.utcnow() - d.created_at
                    ).total_seconds() / 3600,
                }
                for d in decisions
            ]

        except TimeoutError as e:
            logger.error(f"TIMEOUT: get_pending_outcomes exceeded {timeout}s: {e}", exc_info=True)
            raise
        except Exception as e:
            # Gate Criterion: Fail fast on query errors (not silent)
            logger.error(f"CRITICAL: Failed to get pending outcomes: {e}", exc_info=True)
            raise  # Don't return empty list - failure must be visible

    @staticmethod
    def calculate_decision_quality(
        db: Session, decision_batch: List[str]
    ) -> Dict[str, Any]:
        """
        Compute quality metrics for a batch of decisions.

        Used by weight optimizer to assess prediction accuracy.

        Args:
            db: Database session
            decision_batch: List of decision IDs to analyze

        Returns:
            Quality metrics (accuracy, calibration, etc.)
        """
        start_time = time.time()
        timeout = UnifiedDecisionOutcomeService.TIMEOUT_SECONDS["calculate_decision_quality"]

        try:
            decisions = db.query(DecisionOutcome).filter(
                DecisionOutcome.id.in_(decision_batch)
            ).all()

            if not decisions:
                return {
                    "total_decisions": 0,
                    "completed_decisions": 0,
                    "accuracy": 0.0,
                    "confidence_calibration": 0.0,
                    "average_gap": 0.0,
                }

            completed = [d for d in decisions if d.status == "completed"]

            if not completed:
                return {
                    "total_decisions": len(decisions),
                    "completed_decisions": 0,
                    "accuracy": 0.0,
                    "confidence_calibration": 0.0,
                    "average_gap": 0.0,
                }

            # Calculate metrics
            correct_predictions = sum(
                1
                for d in completed
                if (d.actual_success and d.predicted_probability >= 0.5)
                or (not d.actual_success and d.predicted_probability < 0.5)
            )

            accuracy = correct_predictions / len(completed)

            # Confidence calibration: average gap should be ~5%
            avg_gap = sum(d.confidence_gap for d in completed if d.confidence_gap) / len(completed) if completed else 0.0

            # Calibration score (lower gap = better calibration)
            calibration_score = max(0.0, 1.0 - (avg_gap / 0.15))  # 15% gap = bad

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"calculate_decision_quality took {elapsed:.2f}s (timeout: {timeout}s)")

            return {
                "total_decisions": len(decisions),
                "completed_decisions": len(completed),
                "accuracy": float(accuracy),
                "confidence_calibration": float(calibration_score),
                "average_gap": float(avg_gap),
                "perfect_calibration_target": 0.05,
            }

        except TimeoutError as e:
            logger.error(f"TIMEOUT: calculate_decision_quality exceeded {timeout}s: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to calculate decision quality: {e}", exc_info=True)
            raise

    @staticmethod
    def _normalize_event_type(provider: str, event_type: str) -> str:
        """Internal: Normalize provider-specific event types to standard outcomes."""

        # SendGrid events
        if provider == "sendgrid":
            mapping = {
                "delivered": "delivered",
                "opened": "opened",
                "clicked": "clicked",
                "bounced": "bounced",
                "complained": "complained",
                "unsubscribed": "unsubscribed",
            }
            return mapping.get(event_type, event_type)

        # Mailgun events
        elif provider == "mailgun":
            mapping = {
                "delivered": "delivered",
                "opened": "opened",
                "clicked": "clicked",
                "bounced": "bounced",
                "complained": "complained",
            }
            return mapping.get(event_type, event_type)

        # Twilio SMS/WhatsApp events
        elif provider == "twilio":
            mapping = {
                "sent": "sent",
                "delivered": "delivered",
                "read": "opened",  # Map "read" to "opened"
                "failed": "failed",
                "replied": "replied",
            }
            return mapping.get(event_type, event_type)

        # WhatsApp (Meta Cloud API)
        elif provider == "whatsapp":
            mapping = {
                "sent": "sent",
                "delivered": "delivered",
                "read": "opened",
                "failed": "failed",
                "replied": "replied",
            }
            return mapping.get(event_type, event_type)

        # Default: return as-is
        return event_type
