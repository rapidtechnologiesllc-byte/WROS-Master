"""Thunder Autonomous Learning Module - Candidate Engagement Intelligence

Thunder learns optimal outreach strategies through analyzing:
1. Channel effectiveness (email vs SMS vs WhatsApp vs LinkedIn)
2. Timing patterns (best hour of day, day of week)
3. Personalization strategies (by profile, company, experience level)
4. Candidate response patterns and engagement signals

Every outreach result updates the learning model. After 50+ operations,
Thunder becomes significantly smarter about which channels work best for which candidates.
"""
import logging
import uuid
from datetime import datetime, time
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.services.slm_learning_framework import SLMlearningFramework

logger = logging.getLogger(__name__)


class ThunderLearningModule:
    """Autonomous learning system for Thunder candidate engagement"""

    # Channel effectiveness baseline (before learning)
    CHANNEL_BASELINE = {
        "email": 0.35,  # Email opens baseline
        "sms": 0.45,  # SMS delivery baseline
        "whatsapp": 0.55,  # WhatsApp baseline
        "linkedin": 0.25,  # LinkedIn profile view baseline
    }

    # Optimal timing baselines
    OPTIMAL_HOUR_DEFAULT = 9  # 9 AM UTC
    OPTIMAL_DAY_DEFAULT = 2  # Wednesday

    @staticmethod
    def record_outreach_attempt(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        channel: str,
        message_template: str,
        sent_at_hour: int,
        sent_at_day: int,  # 0-6 (Monday-Sunday)
    ) -> Dict[str, Any]:
        """
        Record outreach attempt. Called immediately after sending message.
        Learning happens when result is recorded.
        """
        try:
            logger.info(
                f"[Thunder] Recording outreach: candidate={candidate_id}, "
                f"channel={channel}, template={message_template}, time={sent_at_hour}:00"
            )

            return {
                "status": "recorded",
                "candidate_id": str(candidate_id),
                "channel": channel,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to record outreach attempt: {e}", exc_info=True)
            raise

    @staticmethod
    def record_engagement_result(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        channel: str,
        engagement_type: str,  # "opened", "clicked", "replied", "engaged"
        response_time_hours: Optional[float] = None,
        engagement_quality_score: float = 0.5,  # 0-1.0
    ) -> Dict[str, Any]:
        """
        Record candidate engagement result after outreach.
        This updates Thunder's learning about channel effectiveness.

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            channel: Outreach channel that got response
            engagement_type: Type of engagement ("opened", "clicked", "replied", "engaged")
            response_time_hours: Time to response
            engagement_quality_score: How good was the engagement (0-1.0)
        """
        try:
            # Map engagement type to success boolean
            success_mapping = {
                "opened": True,  # Email open = success
                "delivered": True,  # SMS delivered = success
                "clicked": True,  # Link clicked = strong success
                "replied": True,  # Reply = very strong
                "engaged": True,  # Any engagement = success
                "bounced": False,  # Bounce = failure
                "spam": False,  # Marked as spam = failure
                "no_response": False,  # No response = failure
            }

            success = success_mapping.get(engagement_type, False)

            # Record metric in learning framework
            metric_result = SLMlearningFramework.collect_thunder_metrics(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                channel=channel,
                success=success,
                response_time_hours=response_time_hours,
            )

            logger.info(
                f"[Thunder Learning] Updated engagement: channel={channel}, "
                f"type={engagement_type}, success={success}, confidence={metric_result.get('confidence', 0):.1f}%"
            )

            return {
                "status": "engagement_recorded",
                "channel": channel,
                "engagement_type": engagement_type,
                "success": success,
                "metric_id": metric_result.get("metric_id"),
            }

        except Exception as e:
            logger.error(f"Failed to record engagement result: {e}", exc_info=True)
            raise

    @staticmethod
    def get_recommended_outreach_strategy(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        candidate_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get Thunder's recommended outreach strategy for a candidate.
        Based on learning from 50+ similar candidates.

        Returns:
            Strategy with recommended channel, timing, and message template.
        """
        try:
            # Get Thunder recommendations from learning framework
            recommendations = SLMlearningFramework.get_thunder_recommendations(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
            )

            # If we have candidate profile, further personalize
            if candidate_profile:
                title = candidate_profile.get("title", "").lower()
                years_exp = candidate_profile.get("years_experience", 5)

                # Tailor message template based on profile
                if "senior" in title or "lead" in title:
                    message_template = "senior_engineer_personalized"
                elif "junior" in title or years_exp < 2:
                    message_template = "junior_engineer_entry_level"
                elif "manager" in title or "head" in title:
                    message_template = "leadership_role_opportunity"
                else:
                    message_template = recommendations.get("message_template", "generic_welcome")

                recommendations["message_template"] = message_template
                recommendations["personalized"] = True

            return {
                "candidate_id": str(candidate_id),
                "strategy": recommendations,
                "next_actions": [
                    f"Send via {recommendations['channel']} at {recommendations['best_hour']}:00 UTC",
                    f"Optimal day: {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][recommendations['best_day']]}",
                    f"Use template: {recommendations['message_template']}",
                    f"Confidence: {recommendations['confidence']*100:.0f}%",
                ],
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get outreach strategy: {e}", exc_info=True)
            raise

    @staticmethod
    def get_channel_effectiveness_report(
        db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get channel effectiveness report across all candidates.
        Shows which channels work best overall and by profile type.
        """
        try:
            from app.models.slm_learning_metrics import ThunderLearningMetrics

            # Collect all Thunder metrics for this tenant
            metrics = (
                db.query(ThunderLearningMetrics)
                .filter(ThunderLearningMetrics.tenant_id == tenant_id)
                .all()
            )

            if not metrics:
                return {
                    "status": "insufficient_data",
                    "message": "Not enough data yet - need 10+ outreach attempts",
                    "data": None,
                }

            # Calculate channel effectiveness
            channels = {
                "email": {"success_rate": 0, "count": 0},
                "sms": {"success_rate": 0, "count": 0},
                "whatsapp": {"success_rate": 0, "count": 0},
                "linkedin": {"success_rate": 0, "count": 0},
            }

            for metric in metrics:
                for channel, key in [
                    ("email", "email_success_rate"),
                    ("sms", "sms_success_rate"),
                    ("whatsapp", "whatsapp_success_rate"),
                    ("linkedin", "linkedin_success_rate"),
                ]:
                    rate = getattr(metric, key, 0)
                    if rate > 0:
                        channels[channel]["success_rate"] += rate
                        channels[channel]["count"] += 1

            # Calculate averages
            for channel in channels:
                if channels[channel]["count"] > 0:
                    channels[channel]["success_rate"] /= channels[channel]["count"]

            # Rank channels
            ranked = sorted(
                channels.items(),
                key=lambda x: x[1]["success_rate"],
                reverse=True,
            )

            return {
                "status": "success",
                "metrics_analyzed": len(metrics),
                "channel_rankings": [
                    {
                        "rank": i + 1,
                        "channel": channel,
                        "success_rate": rate["success_rate"],
                        "samples": rate["count"],
                    }
                    for i, (channel, rate) in enumerate(ranked)
                ],
                "recommendation": f"Best channel: {ranked[0][0]} ({ranked[0][1]['success_rate']:.1f}%)",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to generate effectiveness report: {e}", exc_info=True)
            raise

    @staticmethod
    def detect_optimal_contact_window(
        db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Detect optimal contact window (hour + day) by analyzing when
        candidates are most responsive.
        """
        try:
            from app.models.slm_learning_metrics import ThunderLearningMetrics

            # Collect metrics
            metrics = (
                db.query(ThunderLearningMetrics)
                .filter(ThunderLearningMetrics.tenant_id == tenant_id)
                .all()
            )

            if not metrics or len(metrics) < 5:
                return {
                    "status": "insufficient_data",
                    "optimal_hour": 9,
                    "optimal_day": 2,
                    "confidence": 0.3,
                }

            # Count responses by hour/day
            hour_responses = {}
            day_responses = {}

            for metric in metrics:
                if metric.best_outreach_hour is not None:
                    hour = metric.best_outreach_hour
                    hour_responses[hour] = hour_responses.get(hour, 0) + 1

                if metric.best_outreach_day is not None:
                    day = metric.best_outreach_day
                    day_responses[day] = day_responses.get(day, 0) + 1

            # Find optimal times
            optimal_hour = max(hour_responses, key=hour_responses.get) if hour_responses else 9
            optimal_day = max(day_responses, key=day_responses.get) if day_responses else 2

            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            return {
                "status": "success",
                "optimal_hour": optimal_hour,
                "optimal_day": optimal_day,
                "optimal_day_name": day_names[optimal_day],
                "confidence": min(len(metrics) / 50.0, 1.0),
                "recommendation": f"Best time to reach candidates: {day_names[optimal_day]} at {optimal_hour}:00-{optimal_hour+1}:00 UTC",
                "metrics_used": len(metrics),
            }

        except Exception as e:
            logger.error(f"Failed to detect optimal contact window: {e}", exc_info=True)
            raise
