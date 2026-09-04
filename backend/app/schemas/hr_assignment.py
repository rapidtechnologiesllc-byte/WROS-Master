"""
HR Assignment Schemas
=====================
Pydantic request / response models for the HR Assignment API.
import logging
"""

import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.core.logging import logger

# ---------------------------------------------------------------------------
# Nested user summary (returned inside responses)
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class UserSummary(BaseModel):
    """Lightweight user info embedded in HR assignment responses."""
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class HRAssignmentCreate(BaseModel):
    """Body for POST /hr-assignments/ — create a new HR assignment."""
    candidate_id: str = Field(..., description="Candidate ID to assign HR(s) to")
    hr1_id: str = Field(..., description="Primary HR / Recruiter user ID (required)")
    hr2_id: Optional[str] = Field(
        default=None,
        description="Secondary HR / Recruiter user ID (optional)",
    )

    @field_validator("hr2_id", "hr1_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Treat blank / whitespace-only strings as None to avoid FK violations."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

class HRAssignmentUpdate(BaseModel):
    """Body for PATCH /hr-assignments/{candidate_id} — update an existing assignment."""
    hr1_id: Optional[str] = Field(default=None, description="New primary HR / Recruiter user ID")
    hr2_id: Optional[str] = Field(
        default=None,
        description="New secondary HR / Recruiter user ID (pass null to clear)",
    )
    clear_hr2: bool = Field(
        default=False,
        description="Set to true to explicitly remove the secondary HR assignment",
    )

    @field_validator("hr1_id", "hr2_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Treat blank / whitespace-only strings as None to avoid FK violations."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class HRAssignmentResponse(BaseModel):
    """Full response for a single HR assignment record."""
    id: int
    candidate_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None

    hr1: Optional[UserSummary] = None
    hr2: Optional[UserSummary] = None
    assigned_by: Optional[UserSummary] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class HRAssignmentListResponse(BaseModel):
    """Paginated list of HR assignment records."""
    total: int
    assignments: list[HRAssignmentResponse]
