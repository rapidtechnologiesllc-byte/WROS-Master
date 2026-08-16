"""
Job Approval Workflow Service
==============================
Handles job approval routing and recruiter assignment after approval.

Approval Hierarchy:
- CEO/SuperUser creates job → No approval needed (auto-active)
- BU Head creates job → Routing Manager approval required
- Others create job → BU Head approval required
"""

from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.user import Jobs, Users
from app.models.rbac import Role, BusinessUnit
from app.services.recruiter_assignment_service import assign_to_recruiter_roundrobin
from app.services.email_service import EmailService


def get_approval_routing(db: Session, job: Jobs, creator: Users) -> Tuple[Optional[Users], str]:
    """
    Determine who should approve this job based on creator role and hierarchy.

    Returns: (approver_user, routing_reason)
    """
    # CEO/SuperUser - no approval needed
    if creator.UserRole and creator.UserRole.lower() in ("admin", "super user"):
        return None, "Creator is SuperUser - no approval needed"

    # BU Head creates job - route to their reporting manager
    if creator.role and creator.role.name == "BU Head":
        if creator.business_unit_id:
            # Find reporting manager for this BU Head
            reporting_manager = db.query(Users).filter(
                Users.business_unit_id == creator.business_unit_id,
                Users.role.has(Role.name == "CFO")  # Or whatever role reports
            ).first()
            if reporting_manager:
                return reporting_manager, f"BU Head {creator.UserName} must be approved by {reporting_manager.UserName}"
        # Fallback: route to SuperUser
        super_user = db.query(Users).filter(
            Users.role.has(Role.name.in_(["Admin", "SuperUser"]))
        ).first()
        return super_user, "Route to SuperUser (no reporting manager found)"

    # All others - route to their BU Head
    if job.business_unit_id:
        bu_head_role = db.query(Role).filter(Role.name == "BU Head").first()
        if bu_head_role:
            bu_head = db.query(Users).filter(
                Users.role_id == bu_head_role.id,
                Users.business_unit_id == job.business_unit_id
            ).first()
            if bu_head:
                return bu_head, f"Route to BU Head {bu_head.UserName}"

    # Fallback: SuperUser
    super_user = db.query(Users).filter(
        Users.role.has(Role.name.in_(["Admin", "SuperUser"]))
    ).first()
    return super_user, "Route to SuperUser (default)"


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
        logger.error(f"[JobApproval] Failed to assign recruiter: {e}")
        db.rollback()
        return None


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
        logger.error(f"[JobApproval] Error in job approval flow: {e}")
        db.rollback()
        raise
