"""
Internal HR Notes API
=====================
Private notes that HR team members can attach to a candidate for internal
import logging
tracking. Notes are never exposed to the candidate.

Routes:
  GET  /internal/notes/{candidate_id}  â€” list all notes for a candidate
  POST /internal/notes/{candidate_id}  â€” add a new note to a candidate
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.internal_note import InternalNote
from app.schemas.internal_note import (
    InternalNoteCreate,
    InternalNoteResponse,
    InternalNoteListResponse,
)


router = APIRouter(prefix="/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# GET  /internal/notes/{candidate_id}
# ---------------------------------------------------------------------------

@router.get(
    "/notes/{candidate_id}",
    response_model=InternalNoteListResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all internal HR notes for a candidate",
)
def get_notes_by_candidate(
    candidate_id: str,
    category: Optional[str] = Query(
        default=None,
        description="Filter by note category (e.g. 'General', 'Background Check').",
    ),
    db: Session = Depends(get_db),
):
    """
    Returns all **internal HR notes** for the given candidate, ordered by
    newest first.

    Only HR / Admin users can access this endpoint. Notes are strictly
    internal and **never** exposed to the candidate.

    **Optional query params**:
    - `category` â€” filter to notes matching a specific category tag.
    """
    # Verify the candidate exists
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )

    # Build query
    query = (
        db.query(InternalNote)
        .filter(InternalNote.candidate_id == candidate_id)
    )
    if category:
        query = query.filter(InternalNote.category == category)

    notes = query.order_by(InternalNote.created_at.desc()).all()

    return InternalNoteListResponse(
        candidate_id=candidate_id,
        total=len(notes),
        notes=[InternalNoteResponse.model_validate(n) for n in notes],
    )


# ---------------------------------------------------------------------------
# POST /internal/notes/{candidate_id}
# ---------------------------------------------------------------------------

@router.post(
    "/notes/{candidate_id}",
    dependencies=[Depends(require_resource_permission("resource", "access"))],
    response_model=InternalNoteResponse,
    status_code=201,
    summary="Add an internal HR note to a candidate",
)
def create_note(
    candidate_id: str,
    payload: InternalNoteCreate,
    db: Session = Depends(get_db),
    user=Depends(require_resource_permission("candidates", "edit")),
):
    """
    Creates a new **internal HR note** on a candidate.

    - Notes are private and intended solely for the HR team's tracking.
    - The `category` field is optional and defaults to `"General"`.
    - The note is attributed to the authenticated HR / Admin user.

    **Example categories**: `General`, `Background Check`,
    `Salary Negotiation`, `Reference Check`, `Culture Fit`, `Offer Discussion`.
    """
    # Verify the candidate exists
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
        )

    # Capture author details from the authenticated user
    author_id: str = getattr(user, "UserID", "unknown")
    author_name: str = getattr(user, "UserName", None) or getattr(user, "UserEmail", "HR User")

    note = InternalNote(
        candidate_id=candidate_id,
        content=payload.content,
        category=payload.category or "General",
        created_by_id=author_id,
        created_by_name=author_name,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    logger.info(
        f"[InternalNote] Note #{note.id} created for candidate '{candidate_id}' "
        f"by user '{author_id}' ({author_name})."
    )

    return InternalNoteResponse.model_validate(note)
