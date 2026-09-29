"""Candidate Converted To Employee Handler - Stops Thunder from continuing
to message someone who is now an employee.

Unlike candidate_deleted, the Candidate row still exists after conversion
(it's linked to the new Employee, not removed), so any open AI conversation
for them needs to be explicitly closed - otherwise Thunder would keep
treating them as an active outreach target.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.candidate_ai import CandidateConversation

logger = logging.getLogger(__name__)


def handle_candidate_converted_to_employee(message: Any, db: Session) -> Dict[str, Any]:
    payload = message.payload or {}
    candidate_id = payload.get("candidate_id", "UNKNOWN")
    employee_id = payload.get("employee_id")
    converted_at = payload.get("converted_at")

    closed_count = (
        db.query(CandidateConversation)
        .filter(
            CandidateConversation.candidate_id == candidate_id,
            CandidateConversation.status != "closed",
        )
        .update({"status": "closed"}, synchronize_session=False)
    )
    db.commit()

    logger.info(
        f"[CandidateConvertedToEmployee] candidate_id={candidate_id} "
        f"employee_id={employee_id} closed {closed_count} open conversation(s)"
    )

    return {
        "status": "candidate_conversion_recorded",
        "candidate_id": candidate_id,
        "employee_id": employee_id,
        "conversations_closed": closed_count,
    }
