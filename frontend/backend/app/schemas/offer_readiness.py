"""Pydantic Schemas -- S-053/HRMS-0453 Offer Readiness Check."""
from datetime import datetime
from typing import List

from pydantic import BaseModel


class OfferReadinessResponse(BaseModel):
    is_ready: bool
    blockers: List[str]
    warnings: List[str]
    checked_at: datetime
