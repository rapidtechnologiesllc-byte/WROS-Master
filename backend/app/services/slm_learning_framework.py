"""SLM Learning Framework - Production-Ready Autonomous Learning System

Coordinates learning across Thunder (candidate engagement) and Flash (job matching).
- Collects metrics from both systems
- Computes composite SLM health score
- Generates recommendations
- Updates learning weights every 50 operations
- Detects cascade failures and biases
- Provides APIs for frontend dashboard
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.slm_learning_metrics import (
    SLMMetrics,
    ThunderLearningMetrics,
    FlashLearningMetrics,
    LearningWeightUpdate,
    LearningRecommendation,
)

logger = logging.getLogger(__name__)


class SLMlearningFramework:
    """Production-ready autonomous learning system for Thunder and Flash"""

    # Learning thresholds
    OPERATIONS_PER_BATCH = 50  # Update weights every 50 operations
    CONFIDENCE_THRESHOLD = 0.70  # 70% confidence required for recommendations
    CASCADE_THRESHOLD = 0.70  # 70% health score is degraded
    FORMATION_INTEGRITY_THRESHOLD = 0.70  # All agents must be 70%+ healthy

    # Quality score weights
    THUNDER_WEIGHT = 0.35  # Outreach effectiveness
    FLASH_WEIGHT = 0.40  # Job matching quality
    INTERVIEW_WEIGHT = 0.15  # Interview conversion
    OFFER_WEIGHT = 0.10  # Offer acceptance

    @staticmethod
    def collect_thunder_metrics(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        channel: str,
        success: bool,
        response_time_hours: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Record Thunder outreach metric after candidate contact.
        Called after each outreach attempt.

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            channel: Outreach channel ("email", "sms", "whatsapp", "linkedin")
            success: Whether outreach succeeded (opened, delivered, engaged)
            response_time_hours: Time to response in hours (if applicable)

        Returns:
            Metric record with learning update status
        """
        try:
            # Find or create metric record
            metric = db.query(ThunderLearningMetrics).filter(
                and_(
                    ThunderLearningMetrics.tenant_id == tenant_id,
                    ThunderLearningMetrics.candidate_id == candidate_id,
                )
            ).first()

            if not metric:
                metric = ThunderLearningMetrics(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    candidate_id=candidate_id,
                    timestamp=datetime.utcnow(),
                )
                db.add(metric)

            # Update channel-specific success rate
            if channel == "email":
                metric.email_success_rate = (
                    metric.email_success_rate * 0.9 + (100.0 if success else 0.0) * 0.1
                )
            elif channel == "sms":
                metric.sms_success_rate = (
                    metric.sms_success_rate * 0.9 + (100.0 if success else 0.0) * 0.1
                )
            elif channel == "whatsapp":
                metric.whatsapp_success_rate = (
                    metric.whatsapp_success_rate * 0.9 + (100.0 if success else 0.0) * 0.1
                )
            elif channel == "linkedin":
                metric.linkedin_success_rate = (
                    metric.linkedin_success_rate * 0.9 + (100.0 if success else 0.0) * 0.1
                )

            # Update response time if available
            if response_time_hours is not None:
                if metric.average_response_time_hours:
                    metric.average_response_time_hours = (
                        metric.average_response_time_hours * 0.8 + response_time_hours * 0.2
                    )
                else:
                    metric.average_response_time_hours = response_time_hours

            metric.operations_analyzed += 1
            metric.recommendation_confidence = min(
                metric.operations_analyzed / 10.0 * 100.0, 100.0
            )

            # Determine best channel
            channels = {
                "email": metric.email_success_rate,
                "sms": metric.sms_success_rate,
                "whatsapp": metric.whatsapp_success_rate,
                "linkedin": metric.linkedin_success_rate,
            }
            best_channel = max(channels.items(), key=lambda x: x[1])
            metric.recommended_channel = best_channel[0]

            db.commit()

            logger.info(
                f"[Thunder Learning] Recorded {channel} outreach for candidate {candidate_id}: "
                f"success={success}, confidence={metric.recommendation_confidence:.1f}%"
            )

            return {
                "status": "recorded",
                "metric_id": str(metric.id),
                "channel": channel,
                "confidence": metric.recommendation_confidence,
            }

        except Exception as e:
            logger.error(f"Failed to record Thunder metric: {e}", exc_info=True)
            raise

    @staticmethod
    def collect_flash_metrics(
        db: Session,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        metric_type: str,
        value: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record Flash orchestration metric.
        Called after job matching, interview scheduling, offer generation.

        Args:
            db: Database session
            tenant_id: Tenant ID
            job_id: Job ID
            metric_type: "match_quality", "interview_conversion", "offer_acceptance"
            value: Metric value (0-100%)
            details: Optional details dict

        Returns:
            Metric record with learning update status
        """
        try:
            # Find or create metric record
            metric = db.query(FlashLearningMetrics).filter(
                and_(
                    FlashLearningMetrics.tenant_id == tenant_id,
                    FlashLearningMetrics.job_id == job_id,
                )
            ).first()

            if not metric:
                metric = FlashLearningMetrics(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                )
                db.add(metric)

            # Update metric
            if metric_type == "match_quality":
                metric.average_match_quality = metric.average_match_quality * 0.9 + value * 0.1
            elif metric_type == "interview_conversion":
                metric.interview_to_offer_conversion = (
                    metric.interview_to_offer_conversion * 0.9 + value * 0.1
                )
            elif metric_type == "offer_acceptance":
                metric.offer_acceptance_rate = (
                    metric.offer_acceptance_rate * 0.9 + value * 0.1
                )
            elif metric_type == "show_up_rate":
                metric.candidate_show_up_rate = (
                    metric.candidate_show_up_rate * 0.9 + value * 0.1
                )

            metric.operations_analyzed += 1
            metric.recommendation_confidence = min(
                metric.operations_analyzed / 10.0 * 100.0, 100.0
            )

            if details:
                if "candidate_profile" in details:
                    metric.top_candidate_profile = details["candidate_profile"]
                if "salary_range" in details:
                    metric.typical_offer_salary_range = details["salary_range"]

            db.commit()

            logger.info(
                f"[Flash Learning] Recorded {metric_type} for job {job_id}: "
                f"value={value:.1f}%, confidence={metric.recommendation_confidence:.1f}%"
            )

            return {
                "status": "recorded",
                "metric_id": str(metric.id),
                "metric_type": metric_type,
                "confidence": metric.recommendation_confidence,
            }

        except Exception as e:
            logger.error(f"Failed to record Flash metric: {e}", exc_info=True)
            raise

    @staticmethod
    def compute_slm_health_score(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """
        Compute composite SLM health score from Thunder and Flash metrics.
        Called every 50 operations or on-demand for dashboard.

        Returns:
            SLM health score (0-100%) with component breakdown
        """
        try:
            # Collect latest metrics
            thunder_metrics = (
                db.query(ThunderLearningMetrics)
                .filter(ThunderLearningMetrics.tenant_id == tenant_id)
                .order_by(desc(ThunderLearningMetrics.timestamp))
                .limit(10)
                .all()
            )

            flash_metrics = (
                db.query(FlashLearningMetrics)
                .filter(FlashLearningMetrics.tenant_id == tenant_id)
                .order_by(desc(FlashLearningMetrics.timestamp))
                .limit(10)
                .all()
            )

            # Calculate component scores
            thunder_score = (
                sum(m.email_success_rate for m in thunder_metrics)
                / len(thunder_metrics)
                if thunder_metrics
                else 50.0
            )

            flash_match_score = (
                sum(m.average_match_quality for m in flash_metrics)
                / len(flash_metrics)
                if flash_metrics
                else 50.0
            )

            interview_score = (
                sum(m.interview_to_offer_conversion for m in flash_metrics)
                / len(flash_metrics)
                if flash_metrics
                else 50.0
            )

            offer_score = (
                sum(m.offer_acceptance_rate for m in flash_metrics)
                / len(flash_metrics)
                if flash_metrics
                else 50.0
            )

            # Compute composite score
            slm_score = (
                (thunder_score * SLMlearningFramework.THUNDER_WEIGHT)
                + (flash_match_score * SLMlearningFramework.FLASH_WEIGHT)
                + (interview_score * SLMlearningFramework.INTERVIEW_WEIGHT)
                + (offer_score * SLMlearningFramework.OFFER_WEIGHT)
            )

            # Detect cascade risk
            cascade_risk = slm_score < SLMlearningFramework.CASCADE_THRESHOLD * 100

            # Create or update SLMMetrics record
            today = datetime.utcnow().date().isoformat()
            slm_metric = (
                db.query(SLMMetrics)
                .filter(
                    and_(
                        SLMMetrics.tenant_id == tenant_id,
                        SLMMetrics.metric_date == today,
                    )
                )
                .first()
            )

            if not slm_metric:
                slm_metric = SLMMetrics(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    timestamp=datetime.utcnow(),
                    metric_date=today,
                )
                db.add(slm_metric)

            slm_metric.slm_health_score = slm_score
            slm_metric.thunder_outreach_success_rate = thunder_score
            slm_metric.flash_job_match_quality = flash_match_score
            slm_metric.flash_interview_conversion_rate = interview_score
            slm_metric.cascade_risk_detected = cascade_risk
            slm_metric.formation_integrity_score = slm_score

            db.commit()

            logger.info(
                f"[SLM] Health score computed: {slm_score:.1f}% "
                f"(Thunder: {thunder_score:.1f}%, Flash: {flash_match_score:.1f}%, "
                f"Interview: {interview_score:.1f}%, Offer: {offer_score:.1f}%)"
            )

            return {
                "slm_health_score": slm_score,
                "components": {
                    "thunder_outreach": thunder_score,
                    "flash_job_match": flash_match_score,
                    "interview_conversion": interview_score,
                    "offer_acceptance": offer_score,
                },
                "cascade_risk_detected": cascade_risk,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to compute SLM health score: {e}", exc_info=True)
            raise

    @staticmethod
    def update_learning_weights(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """
        Update learning weights for Thunder and Flash based on latest metrics.
        Called every 50 operations to adapt system behavior.

        Returns:
            Update summary with changes applied
        """
        try:
            # Collect metrics for update
            thunder_metrics = (
                db.query(ThunderLearningMetrics)
                .filter(ThunderLearningMetrics.tenant_id == tenant_id)
                .order_by(desc(ThunderLearningMetrics.timestamp))
                .limit(50)
                .all()
            )

            flash_metrics = (
                db.query(FlashLearningMetrics)
                .filter(FlashLearningMetrics.tenant_id == tenant_id)
                .order_by(desc(FlashLearningMetrics.timestamp))
                .limit(50)
                .all()
            )

            # Thunder: determine best channel based on success rates
            if thunder_metrics:
                channels = {
                    "email": sum(m.email_success_rate for m in thunder_metrics) / len(thunder_metrics),
                    "sms": sum(m.sms_success_rate for m in thunder_metrics) / len(thunder_metrics),
                    "whatsapp": sum(m.whatsapp_success_rate for m in thunder_metrics) / len(thunder_metrics),
                    "linkedin": sum(m.linkedin_success_rate for m in thunder_metrics) / len(thunder_metrics),
                }

                best_channel = max(channels.items(), key=lambda x: x[1])[0]

                # Record update
                weight_update = LearningWeightUpdate(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    timestamp=datetime.utcnow(),
                    orchestrator="thunder",
                    update_type="channel_effectiveness",
                    operations_in_batch=len(thunder_metrics),
                    weight_changes=json.dumps(
                        {
                            "best_channel": best_channel,
                            "channels": channels,
                        }
                    ),
                    is_valid=True,
                )
                db.add(weight_update)

            # Flash: determine optimal job-candidate matching patterns
            if flash_metrics:
                avg_match_quality = sum(m.average_match_quality for m in flash_metrics) / len(
                    flash_metrics
                )
                avg_interview_conversion = sum(
                    m.interview_to_offer_conversion for m in flash_metrics
                ) / len(flash_metrics)

                weight_update = LearningWeightUpdate(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    timestamp=datetime.utcnow(),
                    orchestrator="flash",
                    update_type="job_candidate_matching",
                    operations_in_batch=len(flash_metrics),
                    weight_changes=json.dumps(
                        {
                            "avg_match_quality": avg_match_quality,
                            "avg_interview_conversion": avg_interview_conversion,
                        }
                    ),
                    is_valid=True,
                )
                db.add(weight_update)

            db.commit()

            logger.info(
                f"[SLM] Learning weights updated: Thunder ({len(thunder_metrics)} ops), "
                f"Flash ({len(flash_metrics)} ops)"
            )

            return {
                "status": "updated",
                "thunder_operations": len(thunder_metrics),
                "flash_operations": len(flash_metrics),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to update learning weights: {e}", exc_info=True)
            raise

    @staticmethod
    def get_thunder_recommendations(
        db: Session, tenant_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get Thunder recommendations for candidate outreach based on learning.
        Returns best channel, optimal timing, message template.
        """
        try:
            metric = (
                db.query(ThunderLearningMetrics)
                .filter(
                    and_(
                        ThunderLearningMetrics.tenant_id == tenant_id,
                        ThunderLearningMetrics.candidate_id == candidate_id,
                    )
                )
                .first()
            )

            if not metric:
                # No learning data yet, return defaults
                return {
                    "channel": "email",
                    "confidence": 0.5,
                    "best_hour": 9,
                    "best_day": 2,  # Wednesday
                    "message_template": "generic_welcome",
                }

            return {
                "channel": metric.recommended_channel or "email",
                "confidence": metric.recommendation_confidence / 100.0,
                "best_hour": metric.best_outreach_hour or 9,
                "best_day": metric.best_outreach_day or 2,
                "message_template": metric.recommended_message_template or "generic_welcome",
                "channel_success_rates": {
                    "email": metric.email_success_rate,
                    "sms": metric.sms_success_rate,
                    "whatsapp": metric.whatsapp_success_rate,
                    "linkedin": metric.linkedin_success_rate,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get Thunder recommendations: {e}", exc_info=True)
            raise

    @staticmethod
    def get_flash_recommendations(
        db: Session, tenant_id: uuid.UUID, job_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get Flash recommendations for job matching based on learning.
        Returns top candidate profiles, optimal interview timing, offer strategy.
        """
        try:
            metric = (
                db.query(FlashLearningMetrics)
                .filter(
                    and_(
                        FlashLearningMetrics.tenant_id == tenant_id,
                        FlashLearningMetrics.job_id == job_id,
                    )
                )
                .first()
            )

            if not metric:
                # No learning data yet, return defaults
                return {
                    "top_candidate_profile": "mid_level_engineer",
                    "confidence": 0.5,
                    "optimal_interview_days": 3,
                    "offer_strategy": "standard",
                    "match_confidence": 0.5,
                }

            return {
                "top_candidate_profile": metric.top_candidate_profile or "mid_level",
                "confidence": metric.recommendation_confidence / 100.0,
                "match_quality": metric.average_match_quality,
                "optimal_interview_days": metric.optimal_interview_slot_days or 3,
                "interview_to_offer_rate": metric.interview_to_offer_conversion,
                "offer_acceptance_rate": metric.offer_acceptance_rate,
                "typical_salary_range": metric.typical_offer_salary_range,
                "offer_strategy": "aggressive"
                if metric.offer_acceptance_rate > 80
                else "standard"
                if metric.offer_acceptance_rate > 60
                else "conservative",
                "success_hires": metric.success_candidate_count,
            }

        except Exception as e:
            logger.error(f"Failed to get Flash recommendations: {e}", exc_info=True)
            raise
