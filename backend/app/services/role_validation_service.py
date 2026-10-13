"""
Role Validation Service

Centralized validation for user roles across the entire system.
Ensures UserRole and role_template are synchronized.

CRITICAL: This service prevents HR Managers from being treated as Recruiters
and ensures proper role-based access control across all services.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core import roles
from app.models.user import Users

logger = logging.getLogger(__name__)


class RoleValidationService:
    """Centralized role validation with proper role-template alignment checking."""

    @staticmethod
    def is_recruiter(user: Optional[Users]) -> bool:
        """Check if user is a Recruiter (recruitment role, NOT HR Manager)."""
        if not user or user.terminated_at:
            return False
        # Check both UserRole and role_template for consistency
        if user.UserRole != roles.RECRUITER:
            return False
        # Verify role_template also indicates Recruiter
        if user.role_template and user.role_template.name != "Recruiter":
            logger.warning(
                f"[RoleValidation] User {user.UserID} has UserRole=Recruiter "
                f"but role_template={user.role_template.name} (MISALIGNMENT)"
            )
            return False
        return True

    @staticmethod
    def is_hr_manager(user: Optional[Users]) -> bool:
        """Check if user is an HR Manager (onboarding/employee management, NOT recruitment)."""
        if not user or user.terminated_at:
            return False
        if user.UserRole != roles.HR_MANAGER:
            return False
        # Verify role_template also indicates HR Manager
        if user.role_template and user.role_template.name != "HR Manager":
            logger.warning(
                f"[RoleValidation] User {user.UserID} has UserRole=HR Manager "
                f"but role_template={user.role_template.name} (MISALIGNMENT)"
            )
            return False
        return True

    @staticmethod
    def is_super_user(user: Optional[Users]) -> bool:
        """Check if user is Super User (full system access)."""
        if not user or user.terminated_at:
            return False
        # Check via role_template (database-driven)
        if user.role_template and getattr(user.role_template, 'is_super_user', False):
            return True
        # Fallback to UserRole check
        return user.UserRole == roles.SUPER_USER

    @staticmethod
    def is_admin(user: Optional[Users]) -> bool:
        """Check if user is Admin (organization administrator)."""
        if not user or user.terminated_at:
            return False
        return user.UserRole in (roles.ADMIN, roles.SUPER_USER)

    @staticmethod
    def is_partner(user: Optional[Users]) -> bool:
        """Check if user is Partner (business partner)."""
        if not user or user.terminated_at:
            return False
        return user.UserRole == roles.PARTNER

    @staticmethod
    def is_bu_head(user: Optional[Users]) -> bool:
        """Check if user is BU Head (business unit leader)."""
        if not user or user.terminated_at:
            return False
        return user.UserRole == roles.BU_HEAD

    @staticmethod
    def is_finance_manager(user: Optional[Users]) -> bool:
        """Check if user is Finance Manager."""
        if not user or user.terminated_at:
            return False
        return user.UserRole == roles.FINANCE_MANAGER

    @staticmethod
    def can_be_assigned_to_recruiter_pool(user: Optional[Users]) -> bool:
        """
        CRITICAL: Check if user can be assigned as a recruiter to candidates/jobs.

        Only RECRUITER role can be assigned - NOT HR Manager or any other role.
        This prevents HR Managers from handling recruitment tasks.
        """
        if not user or user.terminated_at:
            return False
        # ONLY Recruiters, NEVER HR Managers
        return RoleValidationService.is_recruiter(user)

    @staticmethod
    def validate_role_template_alignment(user: Users) -> bool:
        """
        Validate that UserRole and role_template are properly synchronized.

        Used as a pre-insert/pre-update hook to ensure consistency.

        Args:
            user: User to validate

        Returns:
            True if aligned, False otherwise

        Raises:
            ValueError: If roles are misaligned
        """
        if not user.UserRole or not user.role_template:
            # Allow None values (might be in transition)
            return True

        # Define valid mappings between UserRole and role_template.name
        ROLE_MAPPINGS = {
            roles.RECRUITER: "Recruiter",
            roles.HR_MANAGER: "HR Manager",
            roles.SUPER_USER: "Super User",
            roles.ADMIN: "Admin",
            roles.PARTNER: "Partner",
            roles.BU_HEAD: "BU Head",
            roles.FINANCE_MANAGER: "Finance Manager",
        }

        if user.UserRole not in ROLE_MAPPINGS:
            raise ValueError(f"Invalid UserRole: {user.UserRole}")

        expected_template_name = ROLE_MAPPINGS[user.UserRole]
        if user.role_template.name != expected_template_name:
            raise ValueError(
                f"Role misalignment for {user.UserID}: "
                f"UserRole='{user.UserRole}' requires role_template.name='{expected_template_name}' "
                f"but got '{user.role_template.name}'"
            )

        return True

    @staticmethod
    def get_role_display_name(user: Optional[Users]) -> str:
        """Get human-readable role name for display."""
        if not user:
            return "Unknown"
        return user.UserRole or "Unassigned"

    @staticmethod
    def log_role_check(user: Optional[Users], check_type: str, result: bool) -> None:
        """Log role validation checks for audit trail."""
        if user:
            logger.debug(
                f"[RoleValidation] {check_type}: user={user.UserID} role={user.UserRole} result={result}"
            )
