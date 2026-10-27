"""Learning Event Collector - Unified data collection from all 6 modules

Central service that all modules (Thunder, Flash, Interview, Offer, Finance, Employee)
use to record outcomes in standard format. Enables cascade analysis and cross-module learning.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.learning_events import (
    LearningEvent,
    LearningEventBatch,
    SegmentLearningProfile,
)

logger = logging.getLogger(__name__)


def _tenant_key(tenant_id) -> str:
    """Every learning table keys the tenant as text. Comparing that column with the integer
    tenant id is a PostgreSQL error, and it aborted the caller's whole transaction: the Thunder
    first engagement of every new candidate failed on it (2026-10-24)."""
    if tenant_id is None:
        raise ValueError("Learning events need a tenant")
    return str(tenant_id)


class LearningEventCollector:
    """Unified event collection for all learning modules"""

    @staticmethod
    def record_event(
        db: Session,
        tenant_id: str,
        module: str,  # thunder, flash, interview, offer, finance, employee
        action_type: str,  # email_sent, interview_scheduled, offer_accepted, etc.
        entity_type: str,  # candidate, job, interview, offer, project, employee
        entity_id: str,  # ID of entity (candidate_id, job_id, etc.)
        predicted_outcome: Optional[str] = None,
        predicted_probability: Optional[float] = None,
        actual_outcome: Optional[str] = None,
        actual_success: Optional[bool] = None,
        segment_id: Optional[str] = None,
        cascade_source: Optional[str] = None,
        factors_used: Optional[Dict[str, float]] = None,
        predicted_metadata: Optional[Dict[str, Any]] = None,
        actual_metadata: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        event_timestamp: Optional[datetime] = None,
        expected_outcome_timestamp: Optional[datetime] = None,
        secondary_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a learning event (action + outcome).

        Called by:
        - Thunder: after sending email, after engagement detected
        - Flash: after generating matches, after interview scheduled
        - Interview: after scheduling, after feedback received
        - Offer: after generating, after response received
        - Finance: after project close, monthly metrics
        - Employee: after monthly engagement pulse, on exit

        Args:
            All parameters as documented in LearningEvent model

        Returns:
            Event record with ID and confidence_gap measurement
        """
        tenant_id = _tenant_key(tenant_id)
        try:
            # Calculate confidence gap if both predicted and actual available
            confidence_gap = None
            if predicted_probability is not None and actual_success is not None:
                predicted_for_actual = 1.0 if actual_success else 0.0
                confidence_gap = abs(predicted_probability - predicted_for_actual)

            # Calculate outcome delay
            outcome_delay_hours = None
            if event_timestamp and actual_outcome:
                outcome_delay_hours = (
                    datetime.utcnow() - event_timestamp
                ).total_seconds() / 3600

            # Create event record
            event = LearningEvent(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                module=module,
                action_type=action_type,
                event_id=event_id or str(uuid.uuid4()),
                entity_type=entity_type,
                entity_id=entity_id,
                secondary_entity_id=secondary_entity_id,
                segment_id=segment_id,
                event_timestamp=event_timestamp or datetime.utcnow(),
                expected_outcome_timestamp=expected_outcome_timestamp,
                predicted_outcome=predicted_outcome,
                predicted_probability=predicted_probability,
                predicted_metadata=predicted_metadata,
                actual_outcome=actual_outcome,
                actual_success=actual_success,
                actual_metadata=actual_metadata,
                confidence_gap=confidence_gap,
                factors_used=factors_used,
                outcome_delay_hours=outcome_delay_hours,
                cascade_source=cascade_source,
            )

            with db.begin_nested():  # a failed insert undoes only itself, not the caller's work
                db.add(event)
            db.commit()

            logger.info(
                f"[EventCollector] Event recorded: "
                f"module={module} action={action_type} "
                f"entity={entity_id} "
                f"predicted={predicted_outcome}({'-' if predicted_probability is None else f'{predicted_probability:.2f}'}) "
                f"actual={actual_outcome}({actual_success}) "
                f"gap={confidence_gap}"
            )

            return {
                "event_id": str(event.id),
                "module": module,
                "action_type": action_type,
                "confidence_gap": confidence_gap,
                "status": "recorded",
            }

        except Exception as e:
            logger.error(f"[EventCollector] Failed to record event: {e}", exc_info=True)
            raise

    @staticmethod
    def get_pending_outcomes(
        db: Session,
        tenant_id: str,
        module: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get events that have predicted outcome but no actual outcome yet.
        Used to identify where we're waiting for feedback.
        """
        tenant_id = _tenant_key(tenant_id)
        try:
            query = db.query(LearningEvent).filter(
                LearningEvent.tenant_id == tenant_id,
                LearningEvent.predicted_outcome.isnot(None),
                LearningEvent.actual_outcome.is_(None),
                LearningEvent.event_timestamp
                >= (datetime.utcnow() - timedelta(days=days)),
            )

            if module:
                query = query.filter(LearningEvent.module == module)

            pending = query.all()

            # Group by module and action_type
            grouped = {}
            for event in pending:
                key = f"{event.module}:{event.action_type}"
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(event)

            logger.info(
                f"[EventCollector] Found {len(pending)} pending outcomes "
                f"across {len(grouped)} action types"
            )

            return {
                "total_pending": len(pending),
                "by_action_type": {k: len(v) for k, v in grouped.items()},
                "grouped_events": grouped,
                "timeframe_days": days,
            }

        except Exception as e:
            logger.error(f"[EventCollector] Failed to get pending outcomes: {e}")
            return {"error": str(e), "total_pending": 0}

    @staticmethod
    def get_recent_events(
        db: Session,
        tenant_id: str,
        module: str,
        limit: int = 50,
        days: int = 7,
    ) -> list:
        """Get recent events for a module for learning analysis"""
        from sqlalchemy import desc

        tenant_id = _tenant_key(tenant_id)
        try:
            events = (
                db.query(LearningEvent)
                .filter(
                    LearningEvent.tenant_id == tenant_id,
                    LearningEvent.module == module,
                    LearningEvent.recorded_timestamp
                    >= (datetime.utcnow() - timedelta(days=days)),
                )
                .order_by(desc(LearningEvent.recorded_timestamp))
                .limit(limit)
                .all()
            )

            logger.info(
                f"[EventCollector] Retrieved {len(events)} recent {module} events"
            )
            return events

        except Exception as e:
            logger.error(f"[EventCollector] Failed to get recent events for {module}: {e}", exc_info=True)
            raise

    @staticmethod
    def create_event_batch(
        db: Session,
        tenant_id: str,
        module: str,
        segment_id: Optional[str] = None,
        events: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Create a batch record when weight updates are triggered.
        Used for audit trail and learning history.
        """
        tenant_id = _tenant_key(tenant_id)
        try:
            event_count = len(events) if events else 0

            # Calculate batch metrics
            accuracy = None
            confidence_gap_avg = None

            if events:
                successful = sum(1 for e in events if e.actual_success)
                accuracy = successful / len(events) if len(events) > 0 else 0.0

                gaps = [e.confidence_gap for e in events if e.confidence_gap]
                confidence_gap_avg = (
                    sum(gaps) / len(gaps) if gaps else 0.0
                )

            batch = LearningEventBatch(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                module=module,
                segment_id=segment_id,
                event_count=event_count,
                start_timestamp=min(
                    [e.event_timestamp for e in events], default=datetime.utcnow()
                ),
                end_timestamp=max(
                    [e.event_timestamp for e in events], default=datetime.utcnow()
                ),
                accuracy=accuracy,
                confidence_gap_avg=confidence_gap_avg,
                recorded_timestamp=datetime.utcnow(),
            )

            with db.begin_nested():
                db.add(batch)
            db.commit()

            logger.info(
                f"[EventCollector] Batch created: "
                f"{module}:{segment_id} "
                f"events={event_count} "
                f"accuracy={accuracy:.2%} "
                f"gap_avg={confidence_gap_avg}"
            )

            return {
                "batch_id": str(batch.id),
                "module": module,
                "segment_id": segment_id,
                "event_count": event_count,
                "accuracy": accuracy,
                "confidence_gap_avg": confidence_gap_avg,
            }

        except Exception as e:
            logger.error(f"[EventCollector] Failed to create batch: {e}", exc_info=True)
            raise

    @staticmethod
    def get_segment_profile(
        db: Session,
        tenant_id: str,
        module: str,
        segment_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get or create segment learning profile. Runs in a savepoint: a failure undoes only
        itself and is raised (callers that can do without learning fall back explicitly)."""
        tenant_id = _tenant_key(tenant_id)
        try:
            with db.begin_nested():
                profile = (
                    db.query(SegmentLearningProfile)
                    .filter(
                        SegmentLearningProfile.tenant_id == tenant_id,
                        SegmentLearningProfile.module == module,
                        SegmentLearningProfile.segment_id == segment_id,
                    )
                    .first()
                )
                created = profile is None
                if created:
                    profile = SegmentLearningProfile(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        module=module,
                        segment_id=segment_id,
                        confidence=0.0,  # Start at zero confidence
                        sample_size=0,
                    )
                    db.add(profile)
            if created:
                db.commit()

            return {
                "segment_id": profile.segment_id,
                "module": profile.module,
                "sample_size": profile.sample_size,
                "confidence": profile.confidence,
                "learned_patterns": profile.learned_patterns or {},
                "recommendation": profile.recommendation,
            }

        except Exception as e:
            logger.error(f"[EventCollector] Failed to get segment profile: {e}", exc_info=True)
            raise

    @staticmethod
    def update_segment_patterns(
        db: Session,
        tenant_id: str,
        module: str,
        segment_id: str,
        learned_patterns: Dict[str, Any],
        confidence: float,
        recommendation: str,
    ):
        """Update learned patterns for a segment"""
        tenant_id = _tenant_key(tenant_id)
        try:
            profile = (
                db.query(SegmentLearningProfile)
                .filter(
                    SegmentLearningProfile.tenant_id == tenant_id,
                    SegmentLearningProfile.module == module,
                    SegmentLearningProfile.segment_id == segment_id,
                )
                .first()
            )

            if profile:
                profile.learned_patterns = learned_patterns
                profile.confidence = confidence
                profile.recommendation = recommendation
                profile.last_updated = datetime.utcnow()
                db.commit()

                logger.info(
                    f"[EventCollector] Updated segment patterns: "
                    f"{module}:{segment_id} "
                    f"confidence={confidence:.2f}"
                )

        except Exception as e:
            logger.error(f"[EventCollector] Failed to update patterns: {e}", exc_info=True)
            db.rollback()
            raise
