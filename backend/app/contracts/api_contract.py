"""
STRICT API CONTRACT - Single Source of Truth for all Frontend/Backend Integration

This file defines the EXACT shape of all data that flows between frontend and backend.
ANY deviation from this contract MUST raise an error immediately.

Rules:
1. All requests and responses MUST match these schemas exactly
2. No extra fields allowed (forbid=True)
3. No optional fields unless explicitly marked (Optional[])
4. Type mismatches cause validation failure
5. Backend MUST validate every request/response against these schemas
6. Frontend MUST validate every request/response against these schemas

Created: 2026-08-25
Last Updated: 2026-08-25
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, validator


# ============================================================================
# AUTHENTICATION CONTRACTS
# ============================================================================

class UnifiedLoginRequest(BaseModel):
    """STRICT: Email and password for login - EXACTLY these fields, no extras"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed
        schema_extra = {
            "example": {
                "email": "superuser@blitzenx.com",
                "password": "SuperUser@123"
            }
        }


class ValidateEmailRequest(BaseModel):
    """STRICT: Email validation request - Step 1 of login, only email needed"""
    email: EmailStr = Field(..., description="Email to validate")

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


class UserLoginResponse(BaseModel):
    """STRICT: User login response - exact fields only"""
    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User display name")
    user_email: EmailStr = Field(..., description="User email")
    user_role: str = Field(..., description="Primary user role")
    access_token: str = Field(..., description="JWT token")
    permissions: Dict[str, Any] = Field(..., description="Permission structure")
    roles: Optional[List[str]] = Field(default=None, description="All user roles")

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


class UnifiedLoginResponse(BaseModel):
    """STRICT: Unified login response for both users and candidates"""
    entity_type: str = Field(..., description="'user' or 'candidate'")
    access_token: str = Field(..., description="JWT token")
    is_first_time: bool = Field(default=False)
    mfa_required: bool = Field(default=False)
    mfa_setup_required: bool = Field(default=False)
    email_otp_required: bool = Field(default=False)
    candidate_otp_required: bool = Field(default=False)
    show_2fa_opt_in_popup: bool = Field(default=False)

    # User fields (None for candidates)
    user_role: Optional[str] = Field(default=None)
    user_name: Optional[str] = Field(default=None)
    user_email: Optional[EmailStr] = Field(default=None)
    permissions: Optional[Dict[str, Any]] = Field(default=None)

    # Candidate fields (None for users)
    candidate_id: Optional[str] = Field(default=None)
    candidate_role: Optional[str] = Field(default=None)
    candidate_name: Optional[str] = Field(default=None)
    candidate_email: Optional[EmailStr] = Field(default=None)
    candidate_mobile: Optional[str] = Field(default=None)

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


# ============================================================================
# NAVIGATION CONTRACTS
# ============================================================================

class NavigationItem(BaseModel):
    """STRICT: Single navigation menu item"""
    key: str = Field(..., description="Unique resource key (e.g., 'candidates')")
    label: str = Field(..., description="Display label")
    icon: str = Field(..., description="Icon name (e.g., 'Users', 'Briefcase')")
    route: str = Field(..., description="Frontend route path")

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


class NavigationGroup(BaseModel):
    """STRICT: Group of navigation items"""
    label: str = Field(..., description="Group name (e.g., 'Recruitment')")
    icon: str = Field(..., description="Group icon name")
    items: List[NavigationItem] = Field(..., description="Menu items in this group")

    @validator("items")
    def items_not_empty(cls, v):
        if not v:
            raise ValueError("Navigation group must have at least one item")
        return v

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


class NavigationResponse(BaseModel):
    """STRICT: Complete navigation response structure"""
    data: Dict[str, List[NavigationGroup]] = Field(
        ..., description="Groups key with list of NavigationGroup"
    )

    @validator("data")
    def validate_data_structure(cls, v):
        if "groups" not in v:
            raise ValueError("Navigation response must have 'groups' key in data")
        if not isinstance(v["groups"], list):
            raise ValueError("Navigation groups must be a list")
        return v

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


# ============================================================================
# RESOURCE CONTRACTS (Used by both frontend and backend)
# ============================================================================

MODULES_AND_RESOURCES = {
    "Personal": ["dashboard", "my-tasks", "my-timesheet", "my-expenses", "my-referrals"],
    "Recruitment": ["candidates", "jobs", "submissions", "interviews", "offer-letters",
                    "intervention-queue", "rehire-approval", "candidate-review",
                    "risk-dashboard", "thunder-analytics", "bulk-launch"],
    "Workforce": ["employees", "onboarding", "allocations", "timesheets", "leave-management",
                  "performance-management", "htd-intake", "buddy-program", "convert-to-employee",
                  "utilization-dashboard", "resource-forecast", "employee-in-bench"],
    "Sales": ["clients", "opportunities", "proposals", "sales-ops", "pipeline-management",
              "demand-confirmation"],
    "Project Management": ["projects", "resources", "budget", "schedule", "core-pull"],
    "Finance": ["invoices", "expenses", "payroll", "reports", "budget-management",
                "forecasts", "invoice-management", "finance-operations", "executive-revenue-dashboard"],
    "Reporting": ["analytics", "kpi-dashboard", "data-export", "scheduled-reports", "bi-explorer"],
    "System": ["configuration", "api-keys", "webhooks", "audit-logs", "error-logs",
               "system-health", "slm-training-data", "message-queue", "ticket-routing",
               "ai-config", "locale-currency"],
    "Executive": ["ceo-dashboard", "cfo-dashboard", "partner-dashboard", "executive-signal",
                  "admin-agent-state", "admin-weekly-recap", "bu-head-dashboard"],
    "Admin": ["users-access-control", "admin-settings", "certifications"],
    "Executive Dashboards": ["ceo-dashboard-view", "cfo-dashboard-view", "partner-dashboard-view", "bu-head-dashboard-view"],
    "AI & Automation": ["ask-thunder", "thunder-analytics", "ask-flash", "ai-coaching", "slm-dashboard"],
}


# ============================================================================
# ROLE TEMPLATE CONTRACTS
# ============================================================================

class RolePermissions(BaseModel):
    """STRICT: Permission flags for a resource"""
    can_view: bool = Field(default=True)
    can_create: bool = Field(default=False)
    can_edit: bool = Field(default=False)
    can_delete: bool = Field(default=False)
    display_name: Optional[str] = Field(default=None)
    overridden: bool = Field(default=False)

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


class RoleTemplate(BaseModel):
    """STRICT: Role template definition"""
    id: str = Field(..., description="Unique role template ID")
    name: str = Field(..., description="Role name (e.g., 'SuperUser')")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(default=None)
    permissions: Dict[str, RolePermissions] = Field(default_factory=dict)
    is_system: bool = Field(default=False)
    enabled: bool = Field(default=True)

    class Config:
        extra = "forbid"  # STRICT: No extra fields allowed


# ============================================================================
# VALIDATION FUNCTIONS (Used by both frontend and backend)
# ============================================================================

def validate_login_request(data: Dict[str, Any]) -> UnifiedLoginRequest:
    """STRICT: Validate login request matches contract exactly"""
    try:
        return UnifiedLoginRequest(**data)
    except Exception as e:
        raise ValueError(f"Login request validation failed: {str(e)}")


def validate_login_response(data: Dict[str, Any]) -> UnifiedLoginResponse:
    """STRICT: Validate login response matches contract exactly"""
    try:
        return UnifiedLoginResponse(**data)
    except Exception as e:
        raise ValueError(f"Login response validation failed: {str(e)}")


def validate_navigation_response(data: Dict[str, Any]) -> NavigationResponse:
    """STRICT: Validate navigation response matches contract exactly"""
    try:
        return NavigationResponse(**data)
    except Exception as e:
        raise ValueError(f"Navigation response validation failed: {str(e)}")


def validate_resource_exists(module: str, resource: str) -> bool:
    """STRICT: Verify resource exists in contract"""
    if module not in MODULES_AND_RESOURCES:
        raise ValueError(f"Module '{module}' not found in API contract")
    if resource not in MODULES_AND_RESOURCES[module]:
        raise ValueError(f"Resource '{resource}' not found in module '{module}'")
    return True


def get_all_resources() -> List[str]:
    """Get all resources defined in contract"""
    resources = []
    for module_resources in MODULES_AND_RESOURCES.values():
        resources.extend(module_resources)
    return resources


def get_all_modules() -> List[str]:
    """Get all modules defined in contract"""
    return list(MODULES_AND_RESOURCES.keys())


# ============================================================================
# ENFORCEMENT: Backend must use these schemas
# ============================================================================

__all__ = [
    "UnifiedLoginRequest",
    "ValidateEmailRequest",
    "UnifiedLoginResponse",
    "UserLoginResponse",
    "NavigationItem",
    "NavigationGroup",
    "NavigationResponse",
    "RolePermissions",
    "RoleTemplate",
    "MODULES_AND_RESOURCES",
    "validate_login_request",
    "validate_login_response",
    "validate_navigation_response",
    "validate_resource_exists",
    "get_all_resources",
    "get_all_modules",
]
