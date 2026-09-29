"""Candidate Deleted Handler - Audit trail for candidate deletion.

The Candidate row and its conversations are already gone by the time this
runs (candidate_conversations.candidate_id has ondelete=CASCADE), so there
is no cleanup left to do - this just records the event for downstream/ops
visibility, which is the entire reason the task is queued in the first
place (the caller already emits a separate CandidateEventBus event for
in-process listeners; this queue task is the durable, replay-safe record).
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_candidate_deleted(message: Any, db: Session) -> Dict[str, Any]:
    payload = message.payload or {}
    candidate_id = payload.get("candidate_id", "UNKNOWN")
    candidate_email = payload.get("candidate_email")
    deleted_at = payload.get("deleted_at")

    logger.info(
        f"[CandidateDeleted] candidate_id={candidate_id} email={candidate_email} "
        f"deleted_at={deleted_at}"
    )

    return {
        "status": "candidate_deletion_recorded",
        "candidate_id": candidate_id,
        "deleted_at": deleted_at,
    }
