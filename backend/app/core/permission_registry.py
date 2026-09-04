"""
Centralized Permission Registry - Single Source of Truth

All resources, actions, and permissions defined here.
No hard-coded permission strings anywhere else in codebase.

Admin manages permissions via role templates UI.
Code references ONLY these constants.
"""

# ============================================================================
# RESOURCE DEFINITIONS - Add all resources here
# ============================================================================

RESOURCES = {
    # Recruitment & Candidates
    "candidates": {
        "display_name": "Candidates",
        "module": "Recruitment",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Candidate profiles, applications, screening"
    },
    "jobs": {
        "display_name": "Jobs",
        "module": "Recruitment",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Job postings and requirements"
    },
    "interviews": {
        "display_name": "Interviews",
        "module": "Recruitment",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Interview scheduling and feedback"
    },

    # Projects & Billing
    "projects": {
        "display_name": "Projects",
        "module": "Projects",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Project management and tracking"
    },

    # Employees & HR
    "employees": {
        "display_name": "Employees",
        "module": "HR",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Employee records and management"
    },

    # Administration
    "users": {
        "display_name": "Users",
        "module": "Administration",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "User accounts and access"
    },
    "role_templates": {
        "display_name": "Role Templates",
        "module": "Administration",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Role definitions and permission management"
    },
}

# ============================================================================
# PERMISSION CONSTANTS - Use these in endpoints, NEVER magic strings
# ============================================================================

class Permissions:
    """
    Permission constants for use in endpoint decorators.

    Usage:
        dependencies=[Depends(require_role_template_permission(*Permissions.CANDIDATES_VIEW))]

    Each constant is a tuple: (resource_name, field_name)
    """

    # Candidates
    CANDIDATES_VIEW = ("candidates", "can_view")
    CANDIDATES_CREATE = ("candidates", "can_create")
    CANDIDATES_EDIT = ("candidates", "can_edit")
    CANDIDATES_DELETE = ("candidates", "can_delete")

    # Jobs
    JOBS_VIEW = ("jobs", "can_view")
    JOBS_CREATE = ("jobs", "can_create")
    JOBS_EDIT = ("jobs", "can_edit")
    JOBS_DELETE = ("jobs", "can_delete")

    # Interviews
    INTERVIEWS_VIEW = ("interviews", "can_view")
    INTERVIEWS_CREATE = ("interviews", "can_create")
    INTERVIEWS_EDIT = ("interviews", "can_edit")
    INTERVIEWS_DELETE = ("interviews", "can_delete")

    # Projects
    PROJECTS_VIEW = ("projects", "can_view")
    PROJECTS_CREATE = ("projects", "can_create")
    PROJECTS_EDIT = ("projects", "can_edit")
    PROJECTS_DELETE = ("projects", "can_delete")

    # Employees
    EMPLOYEES_VIEW = ("employees", "can_view")
    EMPLOYEES_CREATE = ("employees", "can_create")
    EMPLOYEES_EDIT = ("employees", "can_edit")
    EMPLOYEES_DELETE = ("employees", "can_delete")

    # Users & Administration
    USERS_VIEW = ("users", "can_view")
    USERS_CREATE = ("users", "can_create")
    USERS_EDIT = ("users", "can_edit")
    USERS_DELETE = ("users", "can_delete")

    ROLE_TEMPLATES_VIEW = ("role_templates", "can_view")
    ROLE_TEMPLATES_CREATE = ("role_templates", "can_create")
    ROLE_TEMPLATES_EDIT = ("role_templates", "can_edit")
    ROLE_TEMPLATES_DELETE = ("role_templates", "can_delete")


# ============================================================================
# PERMISSION GROUPS - Common permission sets
# ============================================================================

PERMISSION_GROUPS = {
    "full_candidates": [
        Permissions.CANDIDATES_VIEW,
        Permissions.CANDIDATES_CREATE,
        Permissions.CANDIDATES_EDIT,
        Permissions.CANDIDATES_DELETE,
    ],
    "read_only_candidates": [
        Permissions.CANDIDATES_VIEW,
    ],
    "recruiter": [
        Permissions.CANDIDATES_VIEW,
        Permissions.CANDIDATES_CREATE,
        Permissions.CANDIDATES_EDIT,
        Permissions.JOBS_VIEW,
        Permissions.INTERVIEWS_VIEW,
        Permissions.INTERVIEWS_CREATE,
    ],
    "admin": [
        # Admin has all permissions (defined by is_super_user check)
    ],
}


def validate_resource(resource_name: str) -> bool:
    """Validate that a resource exists in the registry."""
    return resource_name in RESOURCES


def validate_permission(resource_name: str, field_name: str) -> bool:
    """Validate that a permission exists for a resource."""
    if resource_name not in RESOURCES:
        return False
    return field_name in RESOURCES[resource_name]["actions"]


def get_all_permissions() -> list[tuple[str, str]]:
    """Get all valid permission tuples."""
    perms = []
    for resource_name, resource_config in RESOURCES.items():
        for action in resource_config["actions"]:
            perms.append((resource_name, action))
    return perms
