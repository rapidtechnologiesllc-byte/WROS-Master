"""
Candidate Ownership Schemas
===========================
Pydantic request / response models for the candidate pool ownership API.
import logging
"""

import logging
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.candidate_ownership import POOL_BU, POOL_ORG


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class CandidateOwnershipResponse(BaseModel):
    """Current ownership state for a candidate."""
    candidate_id: str
    pool_status: str                           # "Org Pool" | "BU Owned"
    owned_by_bu_id: Optional[int] = None
    owned_by_bu_name: Optional[str] = None
    ownership_reason: Optional[str] = None
    bu_owned_since: Optional[datetime] = None
    bu_ownership_expires_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CandidateOwnershipListItem(BaseModel):
    """Summary row for the all-candidates list."""
    candidate_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    pool_status: str
    owned_by_bu_name: Optional[str] = None
    bu_ownership_expires_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CandidateOwnershipListResponse(BaseModel):
    total: int
    candidates: List[CandidateOwnershipListItem]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class OwnershipOverrideRequest(BaseModel):
    """Body for HR Admin manual override."""
    pool_status: str = Field(
        ...,
        description=f"New pool status. Allowed: '{POOL_ORG}' | '{POOL_BU}'",
    )
    # Required only when pool_status = "BU Owned"
    bu_id: Optional[int] = Field(
        default=None,
        description="Business Unit ID — required when setting pool_status to 'BU Owned'.",
    )
    reason: str = Field(
        ...,
        description="Reason for the manual override (logged in audit trail).",
    )
