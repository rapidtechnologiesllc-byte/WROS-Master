"""
Schemas for Organizational Structure API requests and responses.
"""
from datetime import datetime
from typing import Optional, List, Union
import logging
from pydantic import BaseModel, Field, field_validator
from app.core.logging import logger

logger = logging.getLogger(__name__)

class OrgPositionResponse(BaseModel):
    """A named organizational position (CEO, Partner, Manager, etc.)"""
    id: int
    name: str = Field(..., description="Position name (e.g., 'CEO', 'Partner', 'Manager')")
    rank: int = Field(..., description="Rank in hierarchy (0=CEO, 1=Partner, ..., 9=Senior Consultant)")
    description: Optional[str] = None
    approves_to_rank: Optional[int] = None
    approves_workflows: Optional[str] = None
    rbac_role_name: Optional[str] = None

    class Config:
        from_attributes = True

class OrgNodeResponse(BaseModel):
    """An instance of a position in the org tree (e.g., 'CEO', 'Partner - BlitzenX', 'Manager - East Coast')"""
    id: str
    tenant_id: int
    tenant_name: Optional[str] = None
    position_id: int
    name: str = Field(..., description="Descriptive name for this specific node")
    parent_id: Optional[str] = None
    department_id: Optional[str] = None
    active: bool = True
    created_at: Union[str, datetime]
    updated_at: Union[str, datetime]

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    class Config:
        from_attributes = True

class DepartmentResponse(BaseModel):
    """A department/team within a business unit"""
    id: str
    tenant_id: int
    tenant_name: Optional[str] = None
    business_unit_id: str
    business_unit_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    cost_center_code: Optional[str] = None
    active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ApprovalChainResponse(BaseModel):
    """A workflow approval route from one position to another"""
    id: int
    tenant_id: int
    from_position_id: int
    to_position_id: int
    workflow: str = Field(..., description="Workflow name (e.g., 'TIMESHEET', 'OFFER_LETTER')")
    auto_escalate: bool = True
    escalate_after_days: Optional[int] = None
    active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrgInitializeRequest(BaseModel):
    """Request to initialize org hierarchy for a tenant"""
    ceo_name: Optional[str] = Field(None, description="Name of the CEO node (defaults to 'CEO')")

class OrgInitializeResponse(BaseModel):
    """Response from org hierarchy initialization"""
    success: bool
    message: str
    tenant_id: int
    ceo_node_id: str
    positions_created: int
    positions_updated: int
    approval_chains_created: int
