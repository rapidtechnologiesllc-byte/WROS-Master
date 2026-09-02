"""
Hiring Manager Validation Service
Manages HM approval checkpoint, email notifications, decision logic, and escalation
"""

import logging
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional, Dict, List
from enum import Enum

from app.models import (
    HiringManagerValidation,
    HMValidationStatus,
    HMValidationResponse,
    Interview,
    Jobs,
)
from app.core.email_service import send_email
from app.core.notification_service import send_dashboard_notification

logger = logging.getLogger(__name__)


class HMValidationService:
    """Service for managing HM validation checkpoint"""

    async def create_validation_request(
        self,
        candidate_id: str,
        job_id: str,
        hiring_manager_id: str,
        match_score: float,
        db,
    ) -> HiringManagerValidation:
        """
        Create new HM validation request after candidate matches to job.
        Sends email and creates dashboard card.
        """
        try:
            # Get job to retrieve timeout config
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job or not job.hm_validation_required:
                return None

            timeout_hours = job.hm_validation_timeout_hours or 24

            validation = HiringManagerValidation(
                id=str(uuid4()),
                candidate_id=candidate_id,
                job_id=job_id,
                hiring_manager_id=hiring_manager_id,
                status=HMValidationStatus.PENDING,
                created_at=datetime.utcnow(),
                due_at=datetime.utcnow() + timedelta(hours=timeout_hours),
                created_by="ai_recruiter",
            )

            db.add(validation)
            db.commit()

            # Send notification email
            await self.send_validation_email(validation=validation, db=db)

            # Create dashboard notification
            await send_dashboard_notification(
                user_id=hiring_manager_id,
                title=f"New Candidate Validation: {candidate_id[:20]}",
                message=f"Please review and validate candidate for {job.jobTitle}",
                link=f"/hiring-manager-validations/{validation.id}",
                priority="high",
            )

            return validation

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error creating validation request: {str(e)}")
            raise

    async def send_validation_email(
        self,
        validation: HiringManagerValidation,
        is_reminder: bool = False,
        db=None,
    ) -> bool:
        """Send HM validation email with candidate details and questions"""
        try:
            job = db.query(Jobs).filter(Jobs.jobID == validation.job_id).first() if db else None

            subject = (
                f"{'REMINDER: ' if is_reminder else ''}Candidate Validation Required - {job.jobTitle if job else 'Job'}"
            )

            # Build email body with candidate data and questions
            email_body = f"""
            <h2>Candidate Validation Required</h2>
            <p>Please review the following candidate and answer the validation questions.</p>

            <h3>Candidate Summary</h3>
            <ul>
                <li><strong>ID:</strong> {validation.candidate_id}</li>
                <li><strong>Job:</strong> {job.jobTitle if job else 'N/A'}</li>
                <li><strong>Match Score:</strong> {getattr(validation, 'match_score', 'N/A')}</li>
            </ul>

            <h3>Validation Questions</h3>
            {self._format_questions_for_email(job.hm_validation_questions if job else [])}

            <h3>Action Required</h3>
            <p>
                <a href="https://hrms.blitzenx.com/hiring-manager-validations/{validation.id}">
                    Click here to review and respond
                </a>
            </p>

            <p><strong>Due Date:</strong> {validation.due_at.strftime('%Y-%m-%d %H:%M %Z')}</p>
            """

            # Send email (implementation depends on email service)
            await send_email(
                to=validation.hiring_manager_id,  # Would need actual email from Users table
                subject=subject,
                body=email_body,
                html=True,
            )

            validation.email_sent_at = datetime.utcnow()
            return True

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error sending validation email: {str(e)}")
            return False

    def _format_questions_for_email(self, questions: List[Dict]) -> str:
        """Format validation questions for email display"""
        if not questions:
            return "<p>No questions configured.</p>"

        html = "<ol>"
        for q in questions:
            html += f"<li><strong>{q.get('question', '')}</strong><br/>"
            if q.get("type") == "text":
                html += "<em>[Text Response]</em>"
            elif q.get("type") == "yes_no":
                html += "<em>[Yes/No]</em>"
            html += "</li>"
        html += "</ol>"
        return html

    async def determine_decision(
        self,
        responses: Dict,
        decision_score: int,
        job_id: str,
        db,
    ) -> Dict:
        """
        Determine HM decision based on responses and scoring.
        Returns decision status (APPROVED/REJECTED/MAYBE).
        """
        try:
            # Get job config
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            # Simple decision logic (can be enhanced with ML)
            # Q4 is typically "Would you recommend proceeding?" (critical question)
            critical_response = responses.get("q_004", responses.get("q_4"))

            if decision_score >= 8 and critical_response in ["yes", "Yes"]:
                return {"status": HMValidationStatus.APPROVED}

            elif decision_score <= 4 or critical_response in ["no", "No"]:
                return {"status": HMValidationStatus.REJECTED}

            else:  # Uncertain (score 5-7)
                return {"status": HMValidationStatus.MAYBE}

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error determining decision: {str(e)}")
            return {"status": HMValidationStatus.MAYBE}  # Default to uncertain on error

    async def schedule_interview_after_approval(
        self,
        validation: HiringManagerValidation,
        db,
    ) -> Optional[Interview]:
        """
        Auto-schedule interview after HM approval (if configured).
        Creates Interview record and sends candidate notification.
        """
        try:
            job = db.query(Jobs).filter(Jobs.jobID == validation.job_id).first()

            if not job or not job.auto_schedule_after_approval:
                return None

            # Create Interview record
            # This would integrate with calendar/scheduling system
            interview = Interview(
                id=None,  # Auto-increment
                interviewID=f"int_{uuid4().hex[:8]}",
                candidate_id=validation.candidate_id,
                status="Scheduled",
                feedback_status="Pending",
            )

            db.add(interview)
            db.commit()

            validation.interview_id = interview.interviewID
            validation.interview_scheduled_at = datetime.utcnow()
            db.commit()

            # Send candidate notification
            await send_email(
                to=validation.candidate_id,
                subject="Interview Scheduled",
                body=f"Your interview for {job.jobTitle} has been scheduled.",
                html=False,
            )

            return interview

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error scheduling interview: {str(e)}")
            raise ValueError("Operation failed")

    async def return_candidate_to_pool(
        self,
        validation: HiringManagerValidation,
        db,
    ) -> bool:
        """
        Return candidate to pool if HM rejects.
        Triggers AI Recruiter to try next best match.
        """
        try:
            # Mark validation as rejected
            validation.status = HMValidationStatus.REJECTED
            validation.next_candidate_tried = False

            db.commit()

            # Trigger AI Recruiter to try next candidate
            # Implementation would call AIRecruiterService.try_next_candidate()

            return True

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error returning candidate to pool: {str(e)}")
            return False

    async def escalate_validation(
        self,
        validation: HiringManagerValidation,
        reason: str,
        db,
    ) -> bool:
        """
        Escalate validation to HM's manager (or auto-reject if timeout exceeded).
        Called for MAYBE responses or expired validations.
        """
        try:
            validation.status = HMValidationStatus.ESCALATED
            validation.escalated_at = datetime.utcnow()
            validation.escalation_reason = reason

            # In production, would fetch HM's manager from org hierarchy
            # For now, mark for manual review
            validation.escalated_to_user_id = None

            db.commit()

            logger.info(f"Escalated validation {validation.id}: {reason}")

            return True

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error escalating validation: {str(e)}")
            return False

    async def handle_expired_validations(self, db) -> int:
        """
        Batch job: find expired validations and escalate them.
        Called by scheduler (e.g., every hour).
        """
        try:
            now = datetime.utcnow()
            expired = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.status == HMValidationStatus.PENDING,
                HiringManagerValidation.due_at < now,
            ).all()

            count = 0
            for validation in expired:
                await self.escalate_validation(
                    validation=validation,
                    reason="Validation timeout exceeded",
                    db=db,
                )
                count += 1

            logger.info(f"Expired and escalated {count} validations")
            return count

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error handling expired validations: {str(e)}")
            return 0

    def generate_interview_briefing(
        self,
        validation: HiringManagerValidation,
        db,
    ) -> Dict:
        """
        Generate briefing for interview panel based on HM's validation answers.
        Summarizes HM's concerns, recommendations, and candidate fit assessment.
        """
        try:
            briefing = {
                "candidate_id": validation.candidate_id,
                "job_id": validation.job_id,
                "hm_recommendation": "APPROVED" if validation.status == HMValidationStatus.APPROVED else "CONDITIONAL",
                "hm_score": validation.decision_score,
                "hm_comment": validation.decision_comment,
                "key_insights": [],
                "areas_to_probe": [],
            }

            # Parse HM responses to extract insights
            if validation.responses:
                for q_id, response in validation.responses.items():
                    if response and response != "yes":
                        briefing["areas_to_probe"].append(f"{q_id}: {response}")

            return briefing

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error generating interview briefing: {str(e)}")
            # CRITICAL FIX: Raise error instead of returning empty dict
            raise Exception(f"Failed to generate interview briefing: {str(e)}")

    async def get_pending_validations(
        self,
        hiring_manager_id: Optional[str] = None,
        limit: int = 10,
        db=None,
    ) -> List[HiringManagerValidation]:
        """Get pending validations for HM dashboard"""
        try:
            query = db.query(HiringManagerValidation).filter(
                HiringManagerValidation.status == HMValidationStatus.PENDING
            )

            if hiring_manager_id:
                query = query.filter(
                    HiringManagerValidation.hiring_manager_id == hiring_manager_id
                )

            return query.order_by(HiringManagerValidation.due_at).limit(limit).all()

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error fetching pending validations: {str(e)}")
            # CRITICAL FIX: Raise error instead of returning empty list
            raise Exception(f"Failed to fetch pending validations: {str(e)}")
