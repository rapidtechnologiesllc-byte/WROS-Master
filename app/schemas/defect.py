"""Defect reporting schemas."""
from pydantic import BaseModel


class DefectReportRequest(BaseModel):
    """User-reported defect/issue."""
    description: str  # Issue description
    affected_screen: str  # Which screen/feature has the issue
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL


class DefectReportResponse(BaseModel):
    """Response after defect is logged."""
    defect_id: str  # Unique defect identifier
    timestamp: str  # ISO timestamp
    message: str  # Confirmation message
