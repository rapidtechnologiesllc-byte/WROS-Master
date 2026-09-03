"""
Candidate History Schemas
=========================
Pydantic request / response models for the candidate history (timeline) API.
import logging
"""

import logging
from app.models.user import Interview
from docx import Document
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Allowed event types — validated on creation
# ---------------------------------------------------------------------------
VALID_EVENT_TYPES = {
    "Applied",
    "Candidate Added",
    "Candidate Edited",
    "Screening",
    "Job Assigned",
    "Interview Scheduled",
    "Feedback Submitted",
    "Interview Completed",
    "Interview Rescheduled",
    "Interview Cancelled",
    "Candidate No Show",
    "Preonboarding Document Rejected",
    "Candidate Archived",
    "Candidate Restored",
    "Offer Updated",
    "Preonboarding Approval",
    "Preonboarding",
    "Preonboarding document verifiy",
    "Offer Released",
    "Offer Accepted",
    "Offer Rejected",
    "Pre-Onboarding",
    "Onboarded",
    "Rejected",
    "Custom",
}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class CandidateHistoryCreateRequest(BaseModel):
    """Body for POST /history/{candidate_id}"""

    event_type: str = Field(
        ...,
        description=(
            "Type of event. Allowed values: "
            "'Applied' | 'Screening' | 'Interview Scheduled' | 'Interview Completed' | "
            "'Offer Released' | 'Offer Accepted' | 'Offer Rejected' | "
            "'Pre-Onboarding' | 'Onboarded' | 'Rejected' | 'Custom'"
        ),
    )
    note: Optional[str] = Field(
        default=None,
        description="Free-text description of the event (e.g. 'Interview scheduled at 3 PM').",
    )
    performed_by_id: Optional[str] = Field(
        default=None,
        description="User ID of the person who performed / triggered this event.",
    )
    performed_by_name: Optional[str] = Field(
        default=None,
        description="Display name snapshot of the person (stored for audit even if user is deleted).",
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Job ID this event is related to.",
    )
    interview_id: Optional[int] = Field(
        default=None,
        description="Interview ID this event is related to.",
    )
    offer_letter_id: Optional[int] = Field(
        default=None,
        description="Offer letter ID this event is related to.",
    )
    event_at: Optional[datetime] = Field(
        default=None,
        description=(
            "ISO-8601 datetime when the event occurred. "
            "Defaults to the current server time if omitted."
        ),
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CandidateHistoryResponse(BaseModel):
    """Single history event in a response."""

    id: int
    candidate_id: str
    event_type: str
    note: Optional[str] = None
    performed_by_id: Optional[str] = None
    performed_by_name: Optional[str] = None
    job_id: Optional[str] = None
    interview_id: Optional[int] = None
    offer_letter_id: Optional[int] = None
    event_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateHistoryListResponse(BaseModel):
    """Paginated list of history events for one candidate."""

    candidate_id: str
    total: int
    events: List[CandidateHistoryResponse]


class CandidateHistoryCreateResponse(BaseModel):
    """Returned after successfully creating a history event."""

    status: str = "success"
    message: str
    event: CandidateHistoryResponse
