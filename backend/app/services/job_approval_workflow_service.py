"""
Job Approval Workflow Service
==============================
import logging
Handles job approval routing and recruiter assignment after approval.

Approval Hierarchy:
- CEO/SuperUser creates job â†’ No approval needed (auto-active)
- BU Head creates job â†’ Routing Manager approval required
- Others create job â†’ BU Head approval required
"""

from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.user import Jobs, Users
from app.models.business_unit import BusinessUnit
from app.services.recruiter_assignment_service import assign_to_recruiter_roundrobin
from app.services.email_service import EmailService


def get_approval_routing(db: Session, job: Jobs, creator: Users) -> Tuple[Optional[Users], str]:
    """
    Determine who should approve this job based on creator permissions and hierarchy.

    Zero-hardcoding: Uses permission checks instead of hardcoded role names.

    Returns: (approver_user, routing_reason)
    """
    # CEO/SuperUser - no approval needed
    # Check via admin.manage permission, not hardcoded role name
    # BU Head creates job - route to their reporting manager
    # Check via 'business_unit.manage' permission (BU Head level)
            # Find manager with admin or finance permissions
            for mgr in managers:
        # Fallback: route to Admin user
        admins = db.query(Users).all()
        for admin in admins:
    # All others - route to their BU Head
    if job.business_unit_id:
        bu_users = db.query(Users).filter(
            Users.business_unit_id == job.business_unit_id
        ).all()

        # Find BU Head (user with business_unit.manage permission in this BU)
        for user in bu_users:
    # Fallback: Admin user
    all_users = db.query(Users).all()
    for admin in all_users:
    return None, "No approver found"


def send_approval_notification_email(db: Session, job: Jobs, approver: Users, reason: str) -> bool:
    """Send email to approver notifying them of job pending approval."""
    try:
        email_service = EmailService()

        subject = f"Job Approval Required: {job.jobTitle}"
        body = f"""
<h2>Job Approval Required</h2>

<p>A new job posting requires your approval:</p>

<table>
  <tr><td><b>Job Title:</b></td><td>{job.jobTitle}</td></tr>
  <tr><td><b>Job ID:</b></td><td>{job.jobID}</td></tr>
  <tr><td><b>Location:</b></td><td>{job.jobLocation}</td></tr>
  <tr><td><b>Positions:</b></td><td>{job.noOfPositions}</td></tr>
  <tr><td><b>Reason:</b></td><td>{reason}</td></tr>
</table>

<p><a href="[WROS_URL]/jobs/{job.jobID}">Click here to approve or reject this job</a></p>

<p>Best regards,<br/>WROS System</p>
"""

        email_service.send_email(
            to_email=approver.UserEmail,
            subject=subject,
            body=body,
            is_html=True
        )

        logger.info(f"[JobApproval] Sent approval notification to {approver.UserEmail} for job {job.jobID}")
        return True

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[JobApproval] Failed to send approval email: {e}")
        return False


def assign_recruiter_on_approval(db: Session, job: Jobs) -> Optional[Users]:
    """Assign recruiter to job on approval using round-robin."""
    try:
        recruiter = assign_to_recruiter_roundrobin(db)

        if recruiter:
            job.recuriterID = recruiter.UserID
            db.commit()
            logger.info(f"[JobApproval] Assigned recruiter {recruiter.UserName} to job {job.jobID}")
            return recruiter
        else:
            logger.warning(f"[JobApproval] No available recruiters to assign to job {job.jobID}")
            return None

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[JobApproval] Failed to assign recruiter: {e}")
        db.rollback()
        raise ValueError("Operation failed")


def parse_skills_from_job_description(job_description: str) -> str:
    """
    Extract skills from job description and format as: Skill:Years:Mandatory

    Example: "We're looking for a senior Java developer with 5 years experience
    in Spring Boot. Knowledge of Docker and AWS is nice to have."

    Returns: "Java:5:yes, Spring Boot:5:yes, Docker:2:no, AWS:2:no"

    Note: This is a simplified version. In production, use LLM-based extraction.
    """
    # For now, return empty string - LLM-based extraction would go here
    # This would call Claude or another LLM to intelligently extract skills
    # with years and mandatory/optional flags
    return ""


def handle_job_creation_approval_flow(
    db: Session,
    job: Jobs,
    creator: Users,
    send_emails: bool = True
) -> dict:
    """
    Complete job creation approval flow:
    1. Determine who should approve
    2. Send notification email
    3. Return approval details
    """
    # Get approval routing
    approver, routing_reason = get_approval_routing(db, job, creator)

    # Send email if approver exists
    email_sent = False
    if approver and send_emails:
        email_sent = send_approval_notification_email(db, job, approver, routing_reason)

    return {
        "job_id": job.jobID,
        "status": "pending_approval",
        "approver_id": approver.UserID if approver else None,
        "approver_name": approver.UserName if approver else "Not found",
        "routing_reason": routing_reason,
        "email_sent": email_sent
    }


def handle_job_approval(
    db: Session,
    job: Jobs,
    approver: Users,
    send_emails: bool = True
) -> dict:
    """
    Complete job approval flow:
    1. Change status to active
    2. Assign recruiter
    3. Send notifications
    """
    try:
        # Assign recruiter
        recruiter = assign_recruiter_on_approval(db, job)

        # In real implementation, would send emails to:
        # - Hiring Manager (job approved)
        # - Assigned Recruiter (new job assigned)

        logger.info(f"[JobApproval] Job {job.jobID} approved. Assigned recruiter: {recruiter.UserName if recruiter else 'None'}")

        return {
            "job_id": job.jobID,
            "status": "active",
            "approved_by": approver.UserName,
            "recruiter_id": recruiter.UserID if recruiter else None,
            "recruiter_name": recruiter.UserName if recruiter else None
        }

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[JobApproval] Error in job approval flow: {e}")
        db.rollback()
        raise
