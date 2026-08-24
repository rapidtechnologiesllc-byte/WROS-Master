"""
Email Sending Tasks
===================

Async email tasks:
- Send individual emails
- Send bulk emails
- Send notifications
"""

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.api.v1.endpoints.admin_queue import TaskStatus, log_task_message
import uuid


@celery_app.task(bind=True, name="tasks.send_email")
def send_email_task(self, to_email: str, subject: str, body: str, html_body: str = None):
    """
    Send a single email asynchronously.
    """
    task_id = str(self.request.id)
    TaskStatus.add_task(task_id, "send_email", "active")
    log_task_message(task_id, f"Sending email to {to_email}: {subject}", "info")

    try:
        # Email sending logic would go here
        # This is a placeholder - integrate with your email service (SendGrid, AWS SES, etc)

        TaskStatus.update_task(task_id, status="completed", progress=100)
        log_task_message(task_id, f"Email sent successfully to {to_email}", "info")

        return {"status": "success", "to_email": to_email}

    except Exception as e:
        log_task_message(task_id, f"Failed to send email: {str(e)}", "error")
        TaskStatus.update_task(task_id, status="failed")
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, name="tasks.send_bulk_emails")
def send_bulk_emails_task(self, recipient_list: list, subject: str, body: str):
    """
    Send emails to multiple recipients.

    Args:
        recipient_list: List of email addresses
        subject: Email subject
        body: Email body
    """
    task_id = str(self.request.id)
    TaskStatus.add_task(task_id, "send_bulk_emails", "active")
    log_task_message(task_id, f"Sending bulk email to {len(recipient_list)} recipients", "info")

    try:
        total = len(recipient_list)
        sent = 0
        failed = 0

        for idx, recipient in enumerate(recipient_list):
            try:
                # Send email logic here (placeholder)
                sent += 1
                progress = int((idx / total) * 100)
                TaskStatus.update_task(task_id, progress=progress)

                if idx % 10 == 0:
                    log_task_message(task_id, f"Sent {sent}/{total} emails", "info")

            except Exception as e:
                failed += 1
                log_task_message(task_id, f"Failed to send to {recipient}: {str(e)}", "warning")

        TaskStatus.update_task(task_id, status="completed", progress=100)
        log_task_message(task_id, f"Bulk email complete: {sent} sent, {failed} failed", "info")

        return {
            "status": "success",
            "total": total,
            "sent": sent,
            "failed": failed,
        }

    except Exception as e:
        log_task_message(task_id, f"Bulk email task failed: {str(e)}", "error")
        TaskStatus.update_task(task_id, status="failed")
        return {"status": "error", "error": str(e)}
