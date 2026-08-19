"""
Async Tasks Module
==================

Background tasks using Celery for:
- Bulk imports
- Resume parsing
- Email sending
- Report generation
- Thunder autonomous cycles
"""

from app.tasks.bulk_import import import_candidates_task, import_candidates_batch_task
from app.tasks.email_tasks import send_email_task, send_bulk_emails_task
from app.tasks.resume_parsing import parse_resume_task
from app.tasks.reporting import generate_report_task

__all__ = [
    "import_candidates_task",
    "import_candidates_batch_task",
    "send_email_task",
    "send_bulk_emails_task",
    "parse_resume_task",
    "generate_report_task",
]
