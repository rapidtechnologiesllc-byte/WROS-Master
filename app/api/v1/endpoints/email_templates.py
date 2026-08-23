"""Email Template Management API for candidate stage progression emails."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.core.dependencies import require_resource_permission, get_current_hr_or_admin
from app.models.email_template import EmailTemplate, EmailTemplateStage
from app.core.logging import logger

router = APIRouter(prefix="/email-templates", tags=["email-templates"])


class EmailTemplateRequest:
    """Request schema for email template."""
    def __init__(self, stage: str, subject: str, body_html: str):
        self.stage = stage
        self.subject = subject
        self.body_html = body_html


class EmailTemplateResponse:
    """Response schema for email template."""
    def __init__(self, template: EmailTemplate):
        self.id = str(template.id)
        self.stage = template.stage
        self.subject = template.subject
        self.body_html = template.body_html
        self.created_by = str(template.created_by) if template.created_by else None
        self.created_at = template.created_at.isoformat() if template.created_at else None
        self.updated_at = template.updated_at.isoformat() if template.updated_at else None


@router.get(
    "",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all email templates"
)
def get_all_templates(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get all email templates for candidate stage progression."""
    templates = db.query(EmailTemplate).all()
    return {
        "total": len(templates),
        "templates": [EmailTemplateResponse(t).__dict__ for t in templates]
    }


@router.get(
    "/{stage}",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get template by stage"
)
def get_template_by_stage(
    stage: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get email template for a specific stage."""
    template = db.query(EmailTemplate).filter(EmailTemplate.stage == stage).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template for stage '{stage}' not found")

    return EmailTemplateResponse(template).__dict__


@router.post(
    "",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Create or update email template"
)
def create_or_update_template(
    stage: str,
    subject: str,
    body_html: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create or update email template for a candidate stage."""
    # Validate stage
    valid_stages = [s.value for s in EmailTemplateStage]
    if stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    # Check if template exists
    template = db.query(EmailTemplate).filter(EmailTemplate.stage == stage).first()

    if template:
        # Update existing
        template.subject = subject
        template.body_html = body_html
        template.updated_at = datetime.utcnow()
        logger.info(f"Updated email template for stage: {stage}")
    else:
        # Create new
        template = EmailTemplate(
            id=uuid.uuid4(),
            stage=stage,
            subject=subject,
            body_html=body_html,
            created_by=getattr(user, "UserID", None),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(template)
        logger.info(f"Created new email template for stage: {stage}")

    db.commit()
    db.refresh(template)

    return {
        "status": "success",
        "message": f"Template for '{stage}' saved successfully",
        "template": EmailTemplateResponse(template).__dict__
    }


@router.put(
    "/{stage}",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Update email template"
)
def update_template(
    stage: str,
    subject: str,
    body_html: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Update an existing email template."""
    template = db.query(EmailTemplate).filter(EmailTemplate.stage == stage).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template for stage '{stage}' not found")

    template.subject = subject
    template.body_html = body_html
    template.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(template)

    logger.info(f"Updated email template for stage: {stage}")

    return {
        "status": "success",
        "message": f"Template for '{stage}' updated successfully",
        "template": EmailTemplateResponse(template).__dict__
    }


@router.post(
    "/{stage}/preview",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Preview email template with sample data"
)
def preview_template(
    stage: str,
    candidate_name: str = "John Doe",
    job_title: str = "Software Engineer",
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Preview how email template will look with sample data."""
    template = db.query(EmailTemplate).filter(EmailTemplate.stage == stage).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template for stage '{stage}' not found")

    # Replace placeholders with sample data
    subject = template.subject.replace("[Candidate Name]", candidate_name).replace("[Job Title]", job_title)
    body = template.body_html.replace("[Candidate Name]", candidate_name).replace("[Job Title]", job_title)

    return {
        "stage": stage,
        "subject": subject,
        "body_html": body,
        "preview_data": {
            "candidate_name": candidate_name,
            "job_title": job_title
        }
    }
