"""Initialize default email templates for candidate stage progression."""

import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.email_template import EmailTemplate


def init_default_email_templates(db: Session):
    """Create default email templates if they don't exist."""

    templates = [
        {
            "stage": "screening",
            "subject": "Your Application for [Job Title] - BlitzenX",
            "body_html": """
            <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#1f2937;">
              Hi [Candidate Name],
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Thank you for your interest in the <strong>[Job Title]</strong> position at BlitzenX.
              We're pleased to inform you that your application has been received and is currently
              under review by our hiring team.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              We appreciate your time and will be in touch soon with updates on your application status.
            </p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
              Best regards,<br/>
              <strong>The BlitzenX Recruitment Team</strong>
            </p>
            """
        },
        {
            "stage": "interview",
            "subject": "Interview Invitation for [Job Title] - BlitzenX",
            "body_html": """
            <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#1f2937;">
              Hi [Candidate Name],
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Great news! You've been selected for an interview for the <strong>[Job Title]</strong> position.
              Our team was impressed by your qualifications and would like to learn more about your experience.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Our recruitment team will be reaching out shortly with interview details, including date, time, and format.
              Please keep an eye on your email for further information.
            </p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
              Best regards,<br/>
              <strong>The BlitzenX Recruitment Team</strong>
            </p>
            """
        },
        {
            "stage": "offer",
            "subject": "Job Offer for [Job Title] - BlitzenX",
            "body_html": """
            <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#1f2937;">
              Hi [Candidate Name],
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Congratulations! We're delighted to extend an offer for the <strong>[Job Title]</strong> position at BlitzenX.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              We were impressed by your qualifications and believe you'll be a great addition to our team.
              Our recruitment team will be sending you the formal offer details shortly, including compensation, benefits, and next steps.
            </p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
              We look forward to working with you!<br/>
              <strong>The BlitzenX Recruitment Team</strong>
            </p>
            """
        },
        {
            "stage": "hired",
            "subject": "Welcome to BlitzenX!",
            "body_html": """
            <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#1f2937;">
              Hi [Candidate Name],
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Welcome to BlitzenX! Your employment for the <strong>[Job Title]</strong> position has been confirmed.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              We're excited to have you join our team! Our Human Resources team will be in touch with onboarding details,
              including orientation schedule, required documentation, and your first day logistics.
            </p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
              Looking forward to seeing you soon!<br/>
              <strong>The BlitzenX Recruitment Team</strong>
            </p>
            """
        },
        {
            "stage": "rejected",
            "subject": "Update on Your Application for [Job Title] - BlitzenX",
            "body_html": """
            <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#1f2937;">
              Hi [Candidate Name],
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              Thank you for your interest in the <strong>[Job Title]</strong> position at BlitzenX.
              We appreciate the time and effort you invested in our interview process.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              While we were impressed by your background, we have decided to move forward with other candidates
              who were a closer fit for this specific role at this time.
            </p>
            <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#4b5563;">
              We encourage you to stay in touch and apply for future opportunities that may be a better match for your skills and experience.
            </p>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
              Best regards,<br/>
              <strong>The BlitzenX Recruitment Team</strong>
            </p>
            """
        }
    ]

    for template_data in templates:
        # Check if template already exists
        existing = db.query(EmailTemplate).filter(
            EmailTemplate.stage == template_data["stage"]
        ).first()

        if not existing:
            template = EmailTemplate(
                id=uuid.uuid4(),
                stage=template_data["stage"],
                subject=template_data["subject"],
                body_html=template_data["body_html"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(template)

    db.commit()
    print("✅ Email templates initialized successfully")
