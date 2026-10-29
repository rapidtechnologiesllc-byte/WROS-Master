"""Message Handler: thunder_process_forwarded_email

A staff member forwarded an email to the HRMS mailbox. Read it (Graph), decide
what it is about and act: create or update the candidate with the resume and a
note, a note on the job or employee, or a task for the forwarder.
See app.services.thunder_mail.forward_intake_service (also for compensation).

Timeout: two Graph reads, one LLM call (retried once) and a SharePoint upload
of up to 10 MB, each with its own HTTP timeout.
"""
import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.forward_intake_service import process_intake

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 180


class ThunderForwardedEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox=None, llm_call: Optional[Callable] = None) -> Dict[str, Any]:
        intake_id = (message.payload or {}).get("intake_id")
        if not intake_id:
            raise ValueError(f"Message {message.id} missing intake_id")
        logger.info(f"[ForwardIntake] handler_start message={message.id} intake={intake_id}")
        try:
            result = process_intake(db, intake_id, mailbox, llm_call=llm_call)
        except Exception:
            db.rollback()
            raise
        logger.info(f"[ForwardIntake] handler_complete intake={intake_id} status={result['status']}")
        return result
