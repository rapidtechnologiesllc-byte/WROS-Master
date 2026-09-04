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


class BusinessUnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Recruiter")
    description: Optional[str] = None


class BusinessUnitResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class BusinessUnitListItem(BaseModel):
    """Lightweight business unit representation for list endpoints."""
    id: int
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}

class SetBusinessUnitRequest(BaseModel):
    user_id: str = Field(..., description="UserID of the user to assign the business unit to")
    business_unit_id: int = Field(..., description="ID of the business unit to assign to the user")

class SetBusinessUnitResponse(BaseModel):
    user_id: str
    business_unit_id: int
    message: str = "Business unit assigned successfully"


# ---------------------------------------------------------------------------
# Department Schemas
# ---------------------------------------------------------------------------

class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Engineering")
    description: Optional[str] = None
    business_unit_id: Optional[int] = Field(
        None, description="ID of the parent Business Unit (optional — can be set later)"
    )


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    business_unit_id: Optional[int] = Field(
        None, description="Reassign to a different Business Unit (set null to unlink)"
    )


class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    business_unit_id: Optional[int] = None
    business_unit_name: Optional[str] = None

    model_config = {"from_attributes": True}


class DepartmentListItem(BaseModel):
    """Lightweight department representation for list endpoints."""
    id: int
    name: str
    description: Optional[str] = None
    business_unit_id: Optional[int] = None
    business_unit_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SetDepartmentRequest(BaseModel):
    user_id: str = Field(..., description="UserID of the user to assign the department to")
    department_id: int = Field(..., description="ID of the department to assign to the user")


class SetDepartmentResponse(BaseModel):
    user_id: str
    department_id: int
    message: str = "Department assigned successfully"


# ---------------------------------------------------------------------------
# BU ↔ Department cross-lookup schemas
# ---------------------------------------------------------------------------

class DepartmentInBU(BaseModel):
    """Compact department info used inside BusinessUnitWithDepartmentsResponse."""
    id: int
    name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class BusinessUnitWithDepartmentsResponse(BaseModel):
    """Business unit with all its linked departments."""
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    departments: List[DepartmentInBU] = []

    model_config = {"from_attributes": True}