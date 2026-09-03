"""
import logging
Interview Feedback Notification Service - DEFECT-13 (CRITICAL)

When interview feedback is submitted, notify all stakeholders:
- Hiring Manager
- BU Head
- All Panel Members
- HR Manager
- Recruiting Manager
"""

import logging
from sqlalchemy.orm import Session
from app.models.interview_pipeline import SubmissionInterview
from app.models.candidate import Candidate
from app.models.user import Users
from app.models.employee import Employee
from app.services.email_service import EmailService
from app.core.logging import logger
from datetime import datetime

logger = logging.getLogger(__name__)

class InterviewFeedbackNotificationService:
    """Handle notifications when interview feedback is submitted."""

    @staticmethod
    def notify_feedback_submitted(
        db: Session,
        interview_id: str,
        feedback_summary: str = None,
    ) -> bool:
        """
        Trigger notification to all stakeholders when feedback is submitted.

        Notifies:
        - Hiring Manager (from job/demand)
        - BU Head (from business unit)
        - All Panel Members (from interview panel)
        - HR Manager
        - Recruiting Manager
        """
        try:
            # Fetch interview with related data
            interview = db.query(SubmissionInterview).filter(
                SubmissionInterview.id == interview_id
            ).first()

            if not interview:
                logger.error(f"Interview {interview_id} not found")
                return False

            # Fetch candidate
            candidate = db.query(Candidate).filter(
                Candidate.id == interview.submission_id
            ).first() if interview.submission_id else None

            if not candidate:
                logger.error(f"Candidate for interview {interview_id} not found")
                return False

            # Collect stakeholders
            stakeholders = set()
            stakeholder_info = {}

            # 1. Hiring Manager (from job or demand)
            if interview.hiring_manager_id:
                hiring_manager = db.query(Users).filter(
                    Users.UserID == interview.hiring_manager_id
                ).first()
                if hiring_manager:
                    stakeholders.add(hiring_manager.UserEmail)
                    stakeholder_info[hiring_manager.UserEmail] = {
                        "name": hiring_manager.UserName,
                        "role": "Hiring Manager"
                    }

            # 2. BU Head
            if interview.bu_head_id:
                bu_head = db.query(Users).filter(
                    Users.UserID == interview.bu_head_id
                ).first()
                if bu_head:
                    stakeholders.add(bu_head.UserEmail)
                    stakeholder_info[bu_head.UserEmail] = {
                        "name": bu_head.UserName,
                        "role": "BU Head"
                    }

            # 3. All Panel Members
            if interview.panel_members:
                # panel_members is a JSON list of user IDs
                panel_ids = interview.panel_members if isinstance(interview.panel_members, list) else []
                for panel_user_id in panel_ids:
                    panel_member = db.query(Users).filter(
                        Users.UserID == panel_user_id
                    ).first()
                    if panel_member:
                        stakeholders.add(panel_member.UserEmail)
                        stakeholder_info[panel_member.UserEmail] = {
                            "name": panel_member.UserName,
                            "role": "Panel Member"
                        }

            # 4. HR Manager & Recruiting Manager (hardcoded for now, should be configurable)
            hr_desk_email = "hr_desk@blitzenx.com"  # Will be in HR Desk
            stakeholders.add(hr_desk_email)

            # Send INDIVIDUAL, ROLE-SPECIFIC emails to each stakeholder
            # Each role gets a tailored notification based on their position in hierarchy
            email_sent_count = 0
            for email in stakeholders:
                try:
                    stakeholder_role = stakeholder_info.get(email, {}).get("role", "Team Member")
                    stakeholder_name = stakeholder_info.get(email, {}).get("name", "Team Member")

                    # Send role-specific notification
                    success = EmailService.send_interview_feedback_notification_individual(
                        recipient_email=email,
                        recipient_name=stakeholder_name,
                        recipient_role=stakeholder_role,
                        candidate_name=f"{candidate.first_name} {candidate.last_name}",
                        candidate_id=candidate.id,
                        interview_date=interview.interview_date,
                        interview_id=interview_id,
                        position_title=interview.position_title or "Position",
                        feedback_giver=interview.feedback_giver_name or "Panel Member",
                        all_panel_members=_format_panel_members(db, interview.panel_members),
                        feedback_summary=feedback_summary,
                    )
                    if success:
                        email_sent_count += 1
                        logger.info(f"Individual feedback notification sent to {stakeholder_role}: {email}")
                    else:
                        logger.warning(f"Failed to send feedback notification to {email} ({stakeholder_role})")
                except Exception as e:
                    logger.error(f"Error: {str(e)}", exc_info=True)
                    logger.error(f"Error sending feedback notification to {email}: {str(e)}")

            logger.info(f"Interview feedback notification sent to {email_sent_count} stakeholders for interview {interview_id}")
            return email_sent_count > 0

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Error in notify_feedback_submitted: {str(e)}")
            return False

def _format_panel_members(db: Session, panel_ids: list) -> list:
    """Format panel member names."""
    if not panel_ids:
        return []

    members = []
    for user_id in panel_ids:
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user:
            members.append(user.UserName)

    return members
