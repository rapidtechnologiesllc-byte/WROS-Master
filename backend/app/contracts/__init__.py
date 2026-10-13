"""
API Contracts - STRICT enforcement of frontend/backend integration

This package contains the authoritative definition of all API schemas.
Both frontend and backend MUST conform to these contracts exactly.
"""

from .api_contract import (
    UnifiedLoginRequest,
    ValidateEmailRequest,
    UnifiedLoginResponse,
    UserLoginResponse,
    NavigationItem,
    NavigationGroup,
    NavigationResponse,
    RolePermissions,
    RoleTemplate,
    MODULES_AND_RESOURCES,
    validate_login_request,
    validate_login_response,
    validate_navigation_response,
    validate_resource_exists,
    get_all_resources,
    get_all_modules,
)

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
