"""Celery tasks for asynchronous candidate creation"""

from celery import shared_task
from app.core.logging import logger
from app.services.message_queue_service import MessageQueueService


@shared_task(bind=True, max_retries=3)
def create_candidate_async(self, email, first_name, last_name, mobile, gender, location, source, tenant_id, user_id, resume_path=None, additional_data=None):
    """Queue candidate creation to message queue for async processing"""
    try:
        if additional_data is None:
            additional_data = {}

        result = MessageQueueService.enqueue(
            task_name='create_candidate',
            data={
                'candidate_email': email,
                'candidate_first_name': first_name,
                'candidate_last_name': last_name,
                'candidate_mobile': mobile,
                'candidate_gender': gender,
                'candidate_current_location': location,
                'candidate_source': source,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'resume_path': resume_path,
                'education_records': additional_data.get('education', []),
                'experience_records': additional_data.get('experience', []),
                'certifications': additional_data.get('certifications', []),
                'skills': additional_data.get('skills', []),
                'current_salary': additional_data.get('current_salary'),
                'expected_salary': additional_data.get('expected_salary'),
            }
        )

        logger.info(f"[Task] Candidate creation queued: {email} (message_id={result.get('message_id')})")

        return {
            'status': 'queued',
            'message_id': result.get('message_id'),
            'task_id': self.request.id,
            'email': email
        }
    except Exception as exc:
        logger.error(f"[Task] Candidate creation failed for {email}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)
