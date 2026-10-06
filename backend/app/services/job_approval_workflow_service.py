"""
Job Approval Workflow Service
==============================
Handles job approval routing and recruiter assignment after approval.

Approval routing (data-driven, no role names):
- Super users need no approval.
- Otherwise the job's BU manager (BusinessUnit.manager_id) approves, unless
  they created the job themselves.
- Fallback: any super user in the tenant.

The approval flow itself is currently disabled in create_job (every job is
published immediately); POST /approve_job still uses handle_job_approval().
"""

import logging
import os
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.user import Jobs, Users
from app.services.recruiter_assignment_service import assign_to_recruiter_roundrobin
from app.services.role_template_permission_service import RoleTemplatePermissionService

logger = logging.getLogger(__name__)


def _first_super_user(db: Session, tenant_id: int, exclude_user_id: Optional[str] = None) -> Optional[Users]:
    users = db.query(Users).filter(Users.tenant_id == tenant_id, Users.terminated_at.is_(None)).all()
    for user in users:
        if user.UserID != exclude_user_id and RoleTemplatePermissionService.is_super_user(db, user.UserID, tenant_id):
            return user
    return None


def get_approval_routing(db: Session, job: Jobs, creator: Optional[Users]) -> Tuple[Optional[Users], str]:
    """Return (approver_user, routing_reason); approver None means no approval needed or none found."""
    tenant_id = (creator.tenant_id if creator else None) or 1
    creator_id = creator.UserID if creator else None

    if creator and RoleTemplatePermissionService.is_super_user(db, creator.UserID, tenant_id):
        return None, "Creator is a super user - no approval needed"

    bu_id = job.business_unit_id or (creator.business_unit_id if creator else None)
    if bu_id:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if bu and bu.manager_id and bu.manager_id != creator_id:
            manager = db.query(Users).filter(Users.UserID == bu.manager_id, Users.terminated_at.is_(None)).first()
            if manager:
                return manager, f"Route to BU manager {manager.UserName or manager.UserEmail}"

    admin = _first_super_user(db, tenant_id, exclude_user_id=creator_id)
    if admin:
        return admin, "Route to super user (no BU manager available)"
    return None, "No approver found"


def send_approval_notification_email(db: Session, job: Jobs, approver: Users, reason: str) -> bool:
    """Email the approver that a job is pending approval. Returns whether it was sent."""
    from app.services.email_service import EmailService

    portal_url = os.getenv("PORTAL_URL", "").rstrip("/")
    link = f'<p><a href="{portal_url}/jobs/{job.jobID}">Open the job to approve or reject it</a></p>' if portal_url else ""
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
{link}
<p>Best regards,<br/>WROS</p>
"""
    try:
        EmailService.send_email(
            to_email=approver.UserEmail,
            subject=f"Job Approval Required: {job.jobTitle}",
            body_content=body,
            is_html=True,
        )
    except Exception as e:
        logger.error(f"[JobApproval] Failed to send approval email for job {job.jobID}: {e}", exc_info=True)
        return False
    logger.info(f"[JobApproval] Sent approval notification to {approver.UserEmail} for job {job.jobID}")
    return True


def assign_recruiter_on_approval(db: Session, job: Jobs) -> Optional[Users]:
    """Assign the least-loaded recruiter to the job (keeps an existing assignment)."""
    if job.recuriterID:
        return db.query(Users).filter(Users.UserID == job.recuriterID).first()

    recruiter = assign_to_recruiter_roundrobin(db)
    if not recruiter:
        logger.warning(f"[JobApproval] No available recruiters to assign to job {job.jobID}")
        return None
    job.recuriterID = recruiter.UserID
    db.commit()
    logger.info(f"[JobApproval] Assigned recruiter {recruiter.UserName} to job {job.jobID}")
    return recruiter


def handle_job_creation_approval_flow(
    db: Session,
    job: Jobs,
    creator: Optional[Users],
    send_emails: bool = True
) -> dict:
    """Route a new job for approval and notify the approver."""
    approver, routing_reason = get_approval_routing(db, job, creator)
    email_sent = bool(approver and send_emails and send_approval_notification_email(db, job, approver, routing_reason))
    return {
        "job_id": job.jobID,
        "status": "pending_approval",
        "approver_id": approver.UserID if approver else None,
        "approver_name": (approver.UserName or approver.UserEmail) if approver else None,
        "routing_reason": routing_reason,
        "email_sent": email_sent,
    }


def handle_job_approval(
    db: Session,
    job: Jobs,
    approver: Users,
    send_emails: bool = True
) -> dict:
    """After a job is approved: assign a recruiter."""
    try:
        recruiter = assign_recruiter_on_approval(db, job)
    except Exception as e:
        logger.error(f"[JobApproval] Recruiter assignment failed for job {job.jobID}: {e}", exc_info=True)
        db.rollback()
        raise

    return {
        "job_id": job.jobID,
        "status": "active",
        "approved_by": approver.UserName or approver.UserEmail,
        "recruiter_id": recruiter.UserID if recruiter else None,
        "recruiter_name": (recruiter.UserName or recruiter.UserEmail) if recruiter else None,
    }
