"""
System Role Constants and Validation

Single source of truth for all valid role names in the system.
Used across all services to avoid magic strings and ensure consistency.

Role Hierarchy:
- SUPER_USER: System administrator (all access)
- ADMIN: Organization administrator
- PARTNER: Business partner/account owner
- BU_HEAD: Business unit leader
- RECRUITER: Recruitment specialist (recruitment pipeline only)
- HR_MANAGER: HR operations (onboarding, employee management only)
- FINANCE_MANAGER: Finance operations
"""

# Role Constants
SUPER_USER = "Super User"
ADMIN = "Admin"
PARTNER = "Partner"
BU_HEAD = "BU Head"
RECRUITER = "Recruiter"
HR_MANAGER = "HR Manager"
FINANCE_MANAGER = "Finance Manager"

# All valid roles in system
VALID_ROLES = {
    SUPER_USER,
    ADMIN,
    PARTNER,
    BU_HEAD,
    RECRUITER,
    HR_MANAGER,
    FINANCE_MANAGER,
}

# Role categories
ADMIN_ROLES = {SUPER_USER, ADMIN}
BUSINESS_ROLES = {PARTNER, BU_HEAD}
OPERATIONAL_ROLES = {RECRUITER, HR_MANAGER, FINANCE_MANAGER}

# Role hierarchy for cascading permissions
ROLE_HIERARCHY = {
    SUPER_USER: ["SUPER_USER", "ADMIN", "PARTNER", "BU_HEAD", "RECRUITER", "HR_MANAGER", "FINANCE_MANAGER"],
    ADMIN: ["ADMIN", "PARTNER", "BU_HEAD", "RECRUITER", "HR_MANAGER", "FINANCE_MANAGER"],
    PARTNER: ["PARTNER", "BU_HEAD", "RECRUITER", "HR_MANAGER", "FINANCE_MANAGER"],
    BU_HEAD: ["BU_HEAD", "RECRUITER", "HR_MANAGER", "FINANCE_MANAGER"],
    RECRUITER: ["RECRUITER"],
    HR_MANAGER: ["HR_MANAGER"],
    FINANCE_MANAGER: ["FINANCE_MANAGER"],
}


def is_valid_role(role_name: str) -> bool:
    """Check if a role name is valid."""
    return role_name in VALID_ROLES


def is_admin_role(role_name: str) -> bool:
    """Check if role has admin-level access."""
    return role_name in ADMIN_ROLES


def is_business_role(role_name: str) -> bool:
    """Check if role is business-level (partner/bu)."""
    return role_name in BUSINESS_ROLES


def is_operational_role(role_name: str) -> bool:
    """Check if role is operational (recruiter/HR/finance)."""
    return role_name in OPERATIONAL_ROLES


def has_superior_role(user_role: str, required_role: str) -> bool:
    """Check if user's role has permissions of required role or higher."""
    if user_role not in ROLE_HIERARCHY:
        return False
    return required_role in ROLE_HIERARCHY[user_role]
