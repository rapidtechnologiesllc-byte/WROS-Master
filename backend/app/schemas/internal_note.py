"""
Internal Note Schemas
=====================
Pydantic models for the Internal HR Note API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class InternalNoteCreate(BaseModel):
    """Payload for creating a new internal HR note on a candidate."""

    content: str = Field(
        ...,
        min_length=1,
        description="The note text (private — not visible to the candidate).",
    )
    category: Optional[str] = Field(
        default="General",
        description=(
            "Optional category tag. "
            "e.g. 'General', 'Background Check', 'Salary Negotiation', 'Reference Check'"
        ),
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class InternalNoteResponse(BaseModel):
    """Single internal note as returned by the API."""

    id: int
    candidate_id: str
    content: str
    category: Optional[str] = None
    created_by_id: str
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InternalNoteListResponse(BaseModel):
    """Response for listing all internal notes for a candidate."""

    candidate_id: str
    total: int
    notes: List[InternalNoteResponse]
