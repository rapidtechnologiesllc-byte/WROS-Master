"""
Pydantic schemas for RBAC — Roles, Permissions, Attributes, and assignment payloads.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Permission Schemas
# ---------------------------------------------------------------------------

class PermissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, example="candidate.view")
    description: Optional[str] = None


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Role Attribute Schemas
# ---------------------------------------------------------------------------

class RoleAttributeCreate(BaseModel):
    attribute_name: str = Field(..., example="pipeline_control")
    attribute_value: bool = False


class RoleAttributeResponse(BaseModel):
    id: int
    role_id: int
    attribute_name: str
    attribute_value: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Role Schemas
# ---------------------------------------------------------------------------

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Recruiter")
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    attributes: List[RoleAttributeResponse] = []
    permissions: List[PermissionResponse] = []

    model_config = {"from_attributes": True}


class RoleListItem(BaseModel):
    """Lightweight role representation for list endpoints."""
    id: int
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assignment Schemas
# ---------------------------------------------------------------------------

class AssignRoleRequest(BaseModel):
    role_id: int = Field(..., description="ID of the role to assign to the user")


class AssignPermissionRequest(BaseModel):
    permission_id: int = Field(..., description="ID of the permission to assign to the role")


# ---------------------------------------------------------------------------
# User Permissions Summary
# ---------------------------------------------------------------------------

class UserPermissionSummary(BaseModel):
    user_id: str
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    permissions: List[str] = []
    attributes: dict = {}
