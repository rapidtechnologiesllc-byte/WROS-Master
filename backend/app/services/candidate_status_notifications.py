"""Every candidate pipeline-status change is emailed to the candidate, with no human step
(CEO 2026-10-13).

One choke point: a hook on CandidateStatus.piplineStatus (app.models.candidate) records each
change during the flush and, once the transaction COMMITS, queues
handle_candidate_status_changed (CandidateStatusChangeHandler) -- so every writer (status
screen, interview verdicts, offers, conversion, rejection paths, job closure) notifies, and a
rolled-back change never does. The wording is a message template per stage
(Settings > Message Templates), seeded once per tenant and editable; it never includes internal
notes or rejection reasons. Kill switch: CANDIDATE_STATUS_EMAILS_ENABLED.
"""
import html
import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# pipeline status -> template key. Internal approval steps share one neutral "final review".
STATUS_TEMPLATE = {
    "Applied": "CANDIDATE_STATUS_APPLIED",
    "Screening": "CANDIDATE_STATUS_SCREENING",
    "Interview": "CANDIDATE_STATUS_INTERVIEW",
    "OfferApproval": "CANDIDATE_STATUS_FINAL_REVIEW",
    "Pre-onboarding-Approval": "CANDIDATE_STATUS_FINAL_REVIEW",
    "Pre-Onboarding": "CANDIDATE_STATUS_PRE_ONBOARDING",
    "Hired": "CANDIDATE_STATUS_HIRED",
    "Onboarded": "CANDIDATE_STATUS_ONBOARDED",
    "EMPLOYEE": "CANDIDATE_STATUS_ONBOARDED",
    "Rejected": "CANDIDATE_STATUS_REJECTED",
}

# Once a candidate is in the process (or out of it), Thunder's nurture outreach stops
THUNDER_OFF_STATUSES = {"Interview", "OfferApproval", "Pre-onboarding-Approval", "Pre-Onboarding",
                        "Hired", "Onboarded", "EMPLOYEE", "Rejected"}

_SIGN = "\n\nBest regards,\nThe {{company_name}} Recruiting Team"
DEFAULT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "CANDIDATE_STATUS_APPLIED": {
        "name": "Candidate status: application received",
        "subject": "We received your application - {{company_name}}",
        "body": "Hi {{candidate_first_name}},\n\nThank you for applying to {{company_name}}. We have received "
                "your application and our team will review it shortly. We'll keep you updated at every step." + _SIGN},
    "CANDIDATE_STATUS_SCREENING": {
        "name": "Candidate status: under review",
        "subject": "Your application is being reviewed",
        "body": "Hi {{candidate_first_name}},\n\nGood news - your profile is now being reviewed by our "
                "recruiting team. We'll be in touch about next steps soon." + _SIGN},
    "CANDIDATE_STATUS_INTERVIEW": {
        "name": "Candidate status: interview stage",
        "subject": "You've been selected to interview",
        "body": "Hi {{candidate_first_name}},\n\nWe were impressed with your background and would like to "
                "interview you. You'll receive the interview details shortly." + _SIGN},
    "CANDIDATE_STATUS_FINAL_REVIEW": {
        "name": "Candidate status: final review",
        "subject": "Your application is in final review",
        "body": "Hi {{candidate_first_name}},\n\nYour application has moved to the final review stage. "
                "We'll share the outcome with you as soon as it's complete." + _SIGN},
    "CANDIDATE_STATUS_PRE_ONBOARDING": {
        "name": "Candidate status: pre-onboarding",
        "subject": "Next steps: getting you ready to join",
        "body": "Hi {{candidate_first_name}},\n\nWe're preparing for you to join {{company_name}}. You'll "
                "receive a short list of documents and details we need from you." + _SIGN},
    "CANDIDATE_STATUS_HIRED": {
        "name": "Candidate status: hired",
        "subject": "Congratulations - welcome to {{company_name}}!",
        "body": "Hi {{candidate_first_name}},\n\nCongratulations! We're delighted to confirm you're joining "
                "{{company_name}}. Your onboarding details will follow." + _SIGN},
    "CANDIDATE_STATUS_ONBOARDED": {
        "name": "Candidate status: onboarded",
        "subject": "Your onboarding is complete",
        "body": "Hi {{candidate_first_name}},\n\nYour onboarding with {{company_name}} is complete - welcome "
                "aboard! Your manager and team will reach out with everything you need." + _SIGN},
    "CANDIDATE_STATUS_REJECTED": {
        "name": "Candidate status: not moving forward",
        "subject": "An update on your application",
        "body": "Hi {{candidate_first_name}},\n\nThank you for your interest in {{company_name}} and for the "
                "time you invested. After careful consideration, we won't be moving forward with your "
                "application at this time. We'll keep your profile on file and reach out if a suitable "
                "role opens." + _SIGN},
}


def template_key_for(status: Optional[str]) -> Optional[str]:
    return STATUS_TEMPLATE.get(status or "")


def seed_templates(db: Session, tenant_id) -> int:
    """Active EMAIL version 1 for every status key the tenant has no version of yet
    (idempotent; admin edits are new versions and are never overwritten). Caller commits."""
    from app.models.message_template import MessageTemplate

    added = 0
    for key, spec in DEFAULT_TEMPLATES.items():
        exists = db.query(MessageTemplate.id).filter(
            MessageTemplate.tenant_id == str(tenant_id), MessageTemplate.template_key == key,
            MessageTemplate.channel == "EMAIL").first()
        if exists:
            continue
        db.add(MessageTemplate(tenant_id=str(tenant_id), template_key=key, template_name=spec["name"],
                               channel="EMAIL", language="en", subject=spec["subject"], body=spec["body"],
                               version=1, is_active=True, created_by="system"))
        added += 1
    return added


def send_status_email(db: Session, candidate, new_status: str) -> Dict:
    """Email the candidate the stage's active template. Returns what happened; raises
    RuntimeError when delivery fails (the queue retries)."""
    from app.core.config import settings
    from app.models.tenant import Tenant
    from app.services.email_service import EmailService
    from app.services.linkedin_pipeline_task_service import is_placeholder_email
    from app.services.message_template_service import render_template

    key = template_key_for(new_status)
    if key is None:
        return {"sent": False, "reason": f"no candidate email for status {new_status!r}"}
    if not settings.CANDIDATE_STATUS_EMAILS_ENABLED:
        return {"sent": False, "reason": "CANDIDATE_STATUS_EMAILS_ENABLED is off"}
    email = candidate.candidateEmail
    if not email or is_placeholder_email(email):
        return {"sent": False, "reason": "no real contact email"}
    if candidate.tenant_id is None:
        raise ValueError(f"Candidate {candidate.candidateID} has no tenant")
    tenant = db.query(Tenant).filter(Tenant.id == candidate.tenant_id).first()
    rendered = render_template(db, key, "EMAIL", str(candidate.tenant_id), {
        "candidate_first_name": candidate.candidateFirstName or "there",
        "company_name": tenant.name if tenant else "our company",
    })
    body_html = "<br>".join(html.escape(line) for line in rendered["rendered_body"].split("\n"))
    result = EmailService.send_email(to_email=email, subject=rendered["rendered_subject"],
                                     body_content=body_html, is_html=True)
    if result.get("status") == "skipped":
        logger.warning(f"[StatusEmail] {candidate.candidateID}: email skipped ({result.get('reason')})")
        return {"sent": False, "reason": result.get("reason"), "template": key}
    if result.get("status") != "success":
        raise RuntimeError(f"Status email to {candidate.candidateID} failed: {result}")
    logger.info(f"[StatusEmail] {candidate.candidateID}: {new_status} -> {key} sent")
    return {"sent": True, "template": key}


def queue_status_change(candidate_id: str, old_status: Optional[str], new_status: str) -> None:
    """After commit: hand the change to the queue (its own session)."""
    from app.services.candidate_event_bus import CandidateEventBus

    try:
        CandidateEventBus.publish_status_changed(candidate_id=candidate_id, old_status=old_status,
                                                 new_status=new_status,
                                                 reason=f"Pipeline status {old_status} -> {new_status}")
    except Exception as exc:
        # The status change itself is committed; losing the notification must be loud
        logger.error(f"[StatusEmail] Could not queue status change for {candidate_id} "
                     f"({old_status} -> {new_status}): {exc}", exc_info=True)
