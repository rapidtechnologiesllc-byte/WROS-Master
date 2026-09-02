"""
Document review <-> Task linkage. Avinash's direct rule (2026-08-05):
"When Pan card is uploaded and approved then it has to be shown in
documents. if it is rejected then the task should be marked as pending
on the candidate and then document should show pan card as pending.
import logging
this is across the board for all documents."

Real architecture: app.models.task.Task never had a candidate/document
link (confirmed by grep -- zero create_task() calls anywhere in the
document or interview flow before this). Added candidate_id/document_id
as nullable columns on the existing real Task table rather than a new
parallel object, matching the already-established "Task is the org's
one activity system" direction from the S-434 build and the HM
candidate-review task-link backlog note.

One Task per (candidate_id, document_id) -- reopened on a second
rejection rather than duplicated, closed on approval. Called from
app.api.v1.endpoints.documents.update_document_verification() after
the document's own is_verified/notes are committed; never blocks that
commit -- task sync failures are logged, not raised, so a Task-side
bug can never prevent HR from actually verifying a document.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.document import CandidateDocument
from app.models.task import Task
from app.services.task_service import create_task

DOCUMENT_LABELS = {
    "pan": "PAN Card",
    "aadhar": "Aadhaar Card",
    "education": "Education Certificate",
    "experience": "Experience Letter",
    "salary_slip": "Salary Slips",
    "bank_statement": "Bank Statement",
    "resume": "Resume",
}


def _document_label(document_type: str) -> str:
    return DOCUMENT_LABELS.get(document_type, (document_type or "Document").replace("_", " ").title())


def _candidate_display_name(candidate: Optional[Candidate]) -> str:
    if not candidate:
        return "Unknown Candidate"
    parts = [candidate.candidateFirstName or "", candidate.candidateLastName or ""]
    return " ".join(p for p in parts if p).strip() or candidate.candidateID


def _existing_document_task(db: Session, candidate_id: str, document_id: int) -> Optional[Task]:
    return (
        db.query(Task)
        .filter(Task.candidate_id == candidate_id, Task.document_id == document_id)
        .order_by(Task.id.desc())
        .first()
    )


def sync_task_for_document_decision(
    db: Session,
    document: CandidateDocument,
    decision: str,
    actor_user_id: Optional[str],
    reason: Optional[str] = None,
) -> None:
    """decision: 'Verified' | 'Rejected' | 'Pending' (matches
    update_document_verification()'s own VALID_STATUSES). 'Pending'
    (a manual reset back to unreviewed) is a no-op here -- neither
    "approve" nor "reject" fired, so there's nothing to open or close.
    Never raises -- see module docstring."""
    try:
        if decision not in ("Verified", "Rejected"):
            return

        candidate = db.query(Candidate).filter(Candidate.candidateID == document.candidate_id).first()
        label = _document_label(document.document_type)
        candidate_name = _candidate_display_name(candidate)

        task = _existing_document_task(db, document.candidate_id, document.id)

        if decision == "Rejected":
            if task is None:
                task = create_task(
                    db,
                    title=f"Re-upload required: {label} -- {candidate_name}",
                    description=f"{label} was rejected for {candidate_name}. Reason: {reason or '(no reason given)'}",
                    priority="MEDIUM",
                    created_by_user_id=actor_user_id,
                    task_type="GENERAL",
                    category="DOCUMENT_REVIEW",
                    # No single assignee -- this is candidate-level work
                    # anyone reviewing documents should see, not one
                    # person's queue item. ORG_WIDE visibility, same as
                    # every other Task with no department/assignee to
                    # scope it by.
                    visibility_scope="ORG_WIDE",
                )
                task.candidate_id = document.candidate_id
                task.document_id = document.id
                db.add(task)
            else:
                # Reopen -- a document can be rejected more than once
                # across re-upload attempts; the same Task tracks the
                # whole thread rather than spawning a new one each time.
                task.status = "NEW"
                task.completed_at = None
                task.description = f"{label} was rejected for {candidate_name}. Reason: {reason or '(no reason given)'}"
                db.add(task)
            db.commit()
            logger.info(f"[DocumentTask] Task {task.id} marked pending -- document {document.id} ({document.document_type}) rejected for candidate {document.candidate_id}")

        elif decision == "Verified" and task is not None and task.status != "COMPLETED":
            task.status = "COMPLETED"
            task.completed_at = datetime.utcnow()
            db.add(task)
            db.commit()
            logger.info(f"[DocumentTask] Task {task.id} closed -- document {document.id} ({document.document_type}) approved for candidate {document.candidate_id}")

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[DocumentTask] Failed to sync task for document {document.id} decision={decision!r}: {exc}")
        db.rollback()
