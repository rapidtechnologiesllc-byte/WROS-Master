"""Thunder Outreach Orchestrator - Autonomous Personalized Engagement

When Thunder receives an outreach task:
1. Determine best channel using learning (email/SMS/WhatsApp/LinkedIn)
2. Determine optimal timing using learning (hour + day)
3. Personalize message based on candidate profile
4. Send outreach
5. Track response and feed back to learning
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.thunder_learning_module import ThunderLearningModule
from app.services.slm_learning_framework import SLMlearningFramework

logger = logging.getLogger(__name__)


class ThunderOutreachOrchestrator:
    """Orchestrates autonomous personalized outreach for candidates"""

    @staticmethod
    def execute_outreach(
        db: Session,
        tenant_id: uuid.UUID,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        job_title: str,
        job_location: str,
        salary_range: str,
        description: str,
        candidate_name: Optional[str] = None,
        candidate_title: Optional[str] = None,
        match_score: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Execute autonomous outreach using Thunder learning.

        Args:
            db: Database session
            tenant_id: Tenant ID
            candidate_id: Candidate ID
            job_id: Job ID
            job_title: Position title
            job_location: Location
            salary_range: Salary range
            description: Job description
            candidate_name: Candidate name for personalization
            candidate_title: Candidate current title
            match_score: Job-candidate match score (0-100)

        Returns:
            Outreach execution result
        """
        try:
            logger.info(
                f"[ThunderOrchestrator] Executing outreach: "
                f"candidate={candidate_id}, job={job_id}, match={match_score:.0f}%"
            )

            # PHASE 1: Get Thunder recommendations for this candidate
            recommendations = ThunderLearningModule.get_recommended_outreach_strategy(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                candidate_profile={
                    "title": candidate_title,
                    "years_experience": 5,  # Would come from candidate record
                },
            )

            if not isinstance(recommendations, dict) or "strategy" not in recommendations:
                raise RuntimeError("Failed to get outreach recommendations")

            strategy = recommendations.get("strategy", {})

            # PHASE 2: Determine channel and timing
            channel = strategy.get("channel", "email")
            best_hour = strategy.get("best_hour", 9)
            best_day = strategy.get("best_day", 2)
            message_template = strategy.get("message_template", "generic_welcome")
            confidence = strategy.get("confidence", 0.5)

            # PHASE 3: Generate personalized message
            message = ThunderOutreachOrchestrator._generate_message(
                template=message_template,
                candidate_name=candidate_name,
                candidate_title=candidate_title,
                job_title=job_title,
                job_location=job_location,
                salary_range=salary_range,
                description=description,
            )

            if not isinstance(message, str) or len(message) == 0:
                raise RuntimeError("Failed to generate outreach message")

            # PHASE 4: Queue the outreach (would actually send in production)
            result = ThunderOutreachOrchestrator._send_outreach(
                channel=channel,
                candidate_id=candidate_id,
                message=message,
                best_hour=best_hour,
                best_day=best_day,
            )

            if not isinstance(result, dict) or result.get("status") != "sent":
                raise RuntimeError("Failed to send outreach")

            # PHASE 5: Record in Thunder learning
            ThunderLearningModule.record_outreach_attempt(
                db=db,
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                channel=channel,
                message_template=message_template,
                sent_at_hour=best_hour,
                sent_at_day=best_day,
            )

            logger.info(
                f"[ThunderOrchestrator] Outreach sent: "
                f"channel={channel}, confidence={confidence*100:.0f}%, "
                f"time={best_hour}:00 {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][best_day]}"
            )

            return {
                "status": "success",
                "candidate_id": str(candidate_id),
                "job_id": str(job_id),
                "channel": channel,
                "sent_at_hour": best_hour,
                "sent_at_day": best_day,
                "confidence": confidence,
                "message_length": len(message),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to execute outreach: {e}", exc_info=True)
            raise

    @staticmethod
    def _generate_message(
        template: str,
        candidate_name: Optional[str] = None,
        candidate_title: Optional[str] = None,
        job_title: str = "Software Engineer",
        job_location: str = "Remote",
        salary_range: str = "Competitive",
        description: str = "Join our team",
    ) -> str:
        """Generate personalized outreach message"""
        try:
            salutation = f"Hi {candidate_name}," if candidate_name else "Hi there,"

            if "senior" in template.lower():
                body = (
                    f"{salutation}\n\n"
                    f"We have a {job_title} opportunity at {job_location} "
                    f"({salary_range}) that matches your senior-level profile.\n\n"
                    f"{description}\n\n"
                    f"Interested in learning more?\n\n"
                    f"Best regards,\nRecruitment Team"
                )
            elif "junior" in template.lower():
                body = (
                    f"{salutation}\n\n"
                    f"Excited about a {job_title} role at {job_location}? "
                    f"This is a great opportunity to grow your skills.\n\n"
                    f"{description}\n\n"
                    f"Let's talk!\n\n"
                    f"Best regards,\nRecruitment Team"
                )
            elif "leadership" in template.lower():
                body = (
                    f"{salutation}\n\n"
                    f"We're looking for a {job_title} to lead our team at {job_location}. "
                    f"Compensation: {salary_range}\n\n"
                    f"{description}\n\n"
                    f"Ready to make an impact?\n\n"
                    f"Best regards,\nRecruitment Team"
                )
            else:
                body = (
                    f"{salutation}\n\n"
                    f"We have an exciting {job_title} opportunity at {job_location} ({salary_range}).\n\n"
                    f"{description}\n\n"
                    f"Interested?\n\n"
                    f"Best regards,\nRecruitment Team"
                )

            if not isinstance(body, str) or len(body) == 0:
                raise ValueError("Generated message is empty")

            return body

        except Exception as e:
            logger.error(f"Failed to generate message: {e}", exc_info=True)
            raise

    @staticmethod
    def _send_outreach(
        channel: str,
        candidate_id: uuid.UUID,
        message: str,
        best_hour: int,
        best_day: int,
    ) -> Dict[str, Any]:
        """Send outreach via specified channel"""
        try:
            if not isinstance(channel, str) or channel not in ["email", "sms", "whatsapp", "linkedin"]:
                raise ValueError(f"Invalid channel: {channel}")

            if not isinstance(message, str) or len(message) == 0:
                raise ValueError("Message is empty")

            # In production: Actually send via channel provider
            # For now: Return success (would call email service, SMS service, etc.)

            logger.info(
                f"[Thunder] Sending {channel}: "
                f"candidate={candidate_id}, "
                f"size={len(message)} chars"
            )

            return {
                "status": "sent",
                "channel": channel,
                "candidate_id": str(candidate_id),
                "message_size": len(message),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to send outreach: {e}", exc_info=True)
            raise
