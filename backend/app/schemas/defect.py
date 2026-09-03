from app.core.logging import logger
"""Defect reporting schemas."""
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DefectReportRequest(BaseModel):
    """User-reported defect/issue."""
    description: str  # Issue description
    affected_screen: str  # Which screen/feature has the issue -- one of the app's real nav module labels, picked from a dropdown client-side
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    blocking_production: bool = False  # If true, backend forces severity to CRITICAL regardless of the value above


class DefectReportResponse(BaseModel):
    """Response after defect is logged."""
    defect_id: str  # Unique defect identifier
    timestamp: str  # ISO timestamp
    message: str  # Confirmation message
