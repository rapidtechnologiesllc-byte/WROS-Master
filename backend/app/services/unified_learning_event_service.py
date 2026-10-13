"""Unified Learning Event Service - Single source of truth for all metric collection

Consolidates functionality from:
- slm_learning_framework.py (Thunder/Flash metric collection)
- learning_event_collector.py (unified event recording)
- thunder_learning_module.py (Thunder-specific metrics)
- flash_learning_module.py (Flash-specific metrics)
- Module-specific metric recording methods

Provides:
- Unified entry point for all 6 modules (Thunder, Flash, Interview, Offer, Finance, Employee)
- Segment-based metric aggregation
- Real-time health score computation
- Metric retrieval for intelligence services
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.learning_events import LearningEvent, SegmentLearningProfile
from app.models.slm_learning_metrics import (
    SLMMetrics,
    ThunderLearningMetrics,
    FlashLearningMetrics,
)

logger = logging.getLogger(__name__)


class UnifiedLearningEventService:
    """Unified metric collection and event recording service"""

    # Learning configuration
    OPERATIONS_PER_BATCH = 50  # Update weights every 50 operations
    CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence for recommendations
    CASCADE_THRESHOLD = 0.70  # Health score threshold
    FORMATION_INTEGRITY_THRESHOLD = 0.70  # All agents must be healthy

    # Metric weights for SLM health score
    THUNDER_WEIGHT = 0.35  # Outreach effectiveness
    FLASH_WEIGHT = 0.40  # Job matching quality
    INTERVIEW_WEIGHT = 0.15  # Interview conversion
    OFFER_WEIGHT = 0.10  # Offer acceptance

    @staticmethod
    def record_event(
        db: Session,
        tenant_id: str,
        module: str,  # thunder, flash, interview, offer, finance, employee
        action_type: str,  # email_sent, interview_scheduled, offer_accepted, etc.
        entity_type: str,  # candidate, job, interview, offer, project, employee
        entity_id: str,  # ID of entity
        predicted_outcome: Optional[str] = None,
        predicted_probability: Optional[float] = None,
        actual_outcome: Optional[str] = None,
        actual_success: Optional[bool] = None,
        segment_id: Optional[str] = None,
        cascade_source: Optional[str] = None,
        factors_used: Optional[Dict[str, float]] = None,
        event_timestamp: Optional[datetime] = None,
        expected_outcome_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Unified entry point for recording any learning event from any module.

        Called by:
        - Thunder: after sending email, after engagement detected
        - Flash: after generating matches, after interview scheduled
        - Interview: after scheduling, after feedback received
        - Offer: after generating, after response received
        - Finance: after project close
        - Employee: after monthly pulse, on exit

        Args:
            db: Database session
            tenant_id: Tenant ID
            module: Module name (thunder, flash, interview, offer, finance, employee)
            action_type: Action type (email_sent, interviewed, offer_accepted, etc.)
            entity_type: Type of entity affected
            entity_id: ID of entity
            predicted_outcome: What was predicted
            predicted_probability: Confidence in prediction (0-1)
            actual_outcome: What actually happened
            actual_success: Whether actual outcome was success
            segment_id: Candidate/job segment for learning
            cascade_source: Which module triggered cascade
            factors_used: Factors used in decision
            event_timestamp: When the action occurred
            expected_outcome_timestamp: When outcome is expected

        Returns:
            Event record with id, timestamp, confidence_gap
        """
        try:
            # Calculate confidence gap
            confidence_gap = None
            if predicted_probability is not None and actual_success is not None:
                predicted_for_actual = 1.0 if actual_success else 0.0
                confidence_gap = abs(predicted_probability - predicted_for_actual)

            # Create learning event record
            event = LearningEvent(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                module=module,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                predicted_outcome=predicted_outcome,
                predicted_probability=predicted_probability,
                actual_outcome=actual_outcome,
                actual_success=actual_success,
                confidence_gap=confidence_gap,
                segment_id=segment_id,
                cascade_source=cascade_source,
                factors_used=json.dumps(factors_used) if factors_used else None,
                timestamp=event_timestamp or datetime.utcnow(),
                expected_outcome_timestamp=expected_outcome_timestamp,
            )
            db.add(event)
            db.commit()

            # Update segment profile if applicable
            if segment_id:
                UnifiedLearningEventService._update_segment_profile(
                    db, tenant_id, segment_id, predicted_probability, actual_success
                )

            return {
                "event_id": event.id,
                "timestamp": event.timestamp,
                "confidence_gap": confidence_gap,
                "segment_id": segment_id,
            }

        except Exception as e:
            logger.error(f"Failed to record learning event: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def record_thunder_metric(
        db: Session,
        tenant_id: str,
        candidate_id: str,
        channel: str,  # email, sms, whatsapp, linkedin
        success: bool,
        response_time_hours: Optional[float] = None,
        predicted_probability: Optional[float] = None,
        segment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record Thunder outreach metric (consolidates SLMlearningFramework.collect_thunder_metrics).

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            channel: Outreach channel (email, sms, whatsapp, linkedin)
            success: Whether outreach succeeded
            response_time_hours: Time to response
            predicted_probability: Confidence in success prediction
            segment_id: Candidate segment

        Returns:
            Metric record with updated success rate
        """
        try:
            # Find or create metric
            metric = db.query(ThunderLearningMetrics).filter(
                and_(
                    ThunderLearningMetrics.tenant_id == tenant_id,
                    ThunderLearningMetrics.candidate_id == candidate_id,
                )
            ).first()

            if not metric:
                metric = ThunderLearningMetrics(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    candidate_id=candidate_id,
                    timestamp=datetime.utcnow(),
                )
                db.add(metric)

            # Update channel success rate (exponential smoothing)
            success_value = 100.0 if success else 0.0
            if channel == "email":
                metric.email_success_rate = (
                    metric.email_success_rate * 0.9 + success_value * 0.1
                )
            elif channel == "sms":
                metric.sms_success_rate = (
                    metric.sms_success_rate * 0.9 + success_value * 0.1
                )
            elif channel == "whatsapp":
                metric.whatsapp_success_rate = (
                    metric.whatsapp_success_rate * 0.9 + success_value * 0.1
                )
            elif channel == "linkedin":
                metric.linkedin_success_rate = (
                    metric.linkedin_success_rate * 0.9 + success_value * 0.1
                )

            db.commit()

            # Also record as learning event for cross-module analysis
            UnifiedLearningEventService.record_event(
                db=db,
                tenant_id=tenant_id,
                module="thunder",
                action_type=f"{channel}_outreach",
                entity_type="candidate",
                entity_id=candidate_id,
                predicted_outcome="engagement",
                predicted_probability=predicted_probability,
                actual_outcome=channel,
                actual_success=success,
                segment_id=segment_id,
            )

            return {
                "candidate_id": candidate_id,
                "channel": channel,
                "success_rate": getattr(metric, f"{channel}_success_rate", 0),
            }

        except Exception as e:
            logger.error(f"Failed to record Thunder metric: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def record_flash_metric(
        db: Session,
        tenant_id: str,
        job_id: str,
        metric_type: str,  # match_quality, interview_scheduling_success, etc.
        metric_value: float,  # 0-1 score
        candidate_id: Optional[str] = None,
        segment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record Flash metric (consolidates FlashLearningModule methods).

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            metric_type: Type of metric (match_quality, interview_success, etc.)
            metric_value: Score 0-1
            candidate_id: Optional candidate ID for match metrics
            segment_id: Job segment

        Returns:
            Metric record with updated score
        """
        try:
            # Find or create metric
            metric = db.query(FlashLearningMetrics).filter(
                and_(
                    FlashLearningMetrics.tenant_id == tenant_id,
                    FlashLearningMetrics.job_id == job_id,
                )
            ).first()

            if not metric:
                metric = FlashLearningMetrics(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                )
                db.add(metric)

            # Update metric with exponential smoothing
            if metric_type == "match_quality":
                metric.match_quality_score = (
                    metric.match_quality_score * 0.9 + metric_value * 0.1
                )
            elif metric_type == "interview_success":
                metric.interview_success_rate = (
                    metric.interview_success_rate * 0.9 + metric_value * 0.1
                )
            elif metric_type == "offer_acceptance":
                metric.offer_acceptance_rate = (
                    metric.offer_acceptance_rate * 0.9 + metric_value * 0.1
                )

            db.commit()

            # Also record as learning event
            UnifiedLearningEventService.record_event(
                db=db,
                tenant_id=tenant_id,
                module="flash",
                action_type=metric_type,
                entity_type="job",
                entity_id=job_id,
                actual_outcome=metric_type,
                actual_success=metric_value >= 0.7,
                segment_id=segment_id,
            )

            return {
                "job_id": job_id,
                "metric_type": metric_type,
                "metric_value": metric_value,
            }

        except Exception as e:
            logger.error(f"Failed to record Flash metric: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def get_segment_profile(
        db: Session, tenant_id: str, segment_id: str
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a segment (candidate/job type)."""
        try:
            profile = db.query(SegmentLearningProfile).filter(
                and_(
                    SegmentLearningProfile.tenant_id == tenant_id,
                    SegmentLearningProfile.segment_id == segment_id,
                )
            ).first()

            if not profile:
                return {
                    "segment_id": segment_id,
                    "event_count": 0,
                    "average_confidence": 0.0,
                    "success_rate": 0.0,
                    "patterns": {},
                }

            return {
                "segment_id": segment_id,
                "event_count": profile.event_count,
                "average_confidence": profile.average_confidence,
                "success_rate": profile.success_rate,
                "patterns": json.loads(profile.patterns) if profile.patterns else {},
            }

        except Exception as e:
            logger.error(f"Failed to get segment profile: {e}", exc_info=True)
            return {"segment_id": segment_id, "error": str(e)}

    @staticmethod
    def get_segment_health_score(
        db: Session, tenant_id: str, segment_id: str
    ) -> float:
        """
        Compute health score for a segment (0-1).
        Higher score = better past predictions for this segment.
        """
        try:
            profile = UnifiedLearningEventService.get_segment_profile(
                db, tenant_id, segment_id
            )

            if profile.get("event_count", 0) == 0:
                return 0.5  # Unknown segment, return neutral

            # Health score based on success rate and confidence accuracy
            success_rate = profile.get("success_rate", 0.5)
            confidence_accuracy = 1.0 - profile.get("average_confidence", 0.5)

            # Weighted average: 70% success rate, 30% confidence accuracy
            health_score = (success_rate * 0.7) + (confidence_accuracy * 0.3)

            return max(0.0, min(1.0, health_score))  # Clamp 0-1

        except Exception as e:
            logger.error(f"Failed to compute segment health score: {e}", exc_info=True)
            return 0.5  # Default to neutral on error

    @staticmethod
    def collect_channel_metrics(
        db: Session, tenant_id: str, channel: str
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a communication channel."""
        try:
            # Query all Thunder metrics for this tenant and channel
            metrics = db.query(ThunderLearningMetrics).filter(
                ThunderLearningMetrics.tenant_id == tenant_id
            ).all()

            if not metrics:
                return {
                    "channel": channel,
                    "success_rate": 0.0,
                    "sample_count": 0,
                }

            # Get channel-specific success rate
            if channel == "email":
                rates = [m.email_success_rate for m in metrics if m.email_success_rate is not None]
            elif channel == "sms":
                rates = [m.sms_success_rate for m in metrics if m.sms_success_rate is not None]
            elif channel == "whatsapp":
                rates = [m.whatsapp_success_rate for m in metrics if m.whatsapp_success_rate is not None]
            elif channel == "linkedin":
                rates = [m.linkedin_success_rate for m in metrics if m.linkedin_success_rate is not None]
            else:
                rates = []

            avg_rate = sum(rates) / len(rates) if rates else 0.0

            return {
                "channel": channel,
                "success_rate": avg_rate,
                "sample_count": len(rates),
            }

        except Exception as e:
            logger.error(f"Failed to collect channel metrics: {e}", exc_info=True)
            return {"channel": channel, "success_rate": 0.0, "error": str(e)}

    @staticmethod
    def _update_segment_profile(
        db: Session,
        tenant_id: str,
        segment_id: str,
        predicted_probability: Optional[float],
        actual_success: Optional[bool],
    ) -> None:
        """Internal: Update segment profile with new event data."""
        try:
            profile = db.query(SegmentLearningProfile).filter(
                and_(
                    SegmentLearningProfile.tenant_id == tenant_id,
                    SegmentLearningProfile.segment_id == segment_id,
                )
            ).first()

            if not profile:
                profile = SegmentLearningProfile(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    segment_id=segment_id,
                )
                db.add(profile)

            # Update event count
            profile.event_count = (profile.event_count or 0) + 1

            # Update average confidence using exponential smoothing
            if predicted_probability is not None:
                old_confidence = profile.average_confidence or 0.5
                profile.average_confidence = (
                    old_confidence * 0.9 + predicted_probability * 0.1
                )

            # Update success rate
            if actual_success is not None:
                old_success_rate = profile.success_rate or 0.5
                success_value = 1.0 if actual_success else 0.0
                profile.success_rate = (
                    old_success_rate * 0.9 + success_value * 0.1
                )

            db.commit()

        except Exception as e:
            logger.warning(f"Failed to update segment profile: {e}")
            db.rollback()
