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
    "timesheets": {
        "display_name": "Timesheets",
        "module": "HR",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Timesheet submission and approval"
    },

    # Finance & Billing
    "invoices": {
        "display_name": "Invoices",
        "module": "Finance",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Invoice generation and management"
    },

    # Sales & Opportunities
    "opportunities": {
        "display_name": "Opportunities",
        "module": "Sales",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Sales opportunities and pipeline"
    },
    "clients": {
        "display_name": "Clients",
        "module": "Sales",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Client accounts and information"
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

    # Agents & Automation
    "agents": {
        "display_name": "Agents",
        "module": "Automation",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Autonomous agents and automation workflows"
    },
    "agent_config": {
        "display_name": "Agent Configuration",
        "module": "Automation",
        "actions": ["can_view", "can_edit"],
        "description": "Agent settings and parameters"
    },
    "agent_performance": {
        "display_name": "Agent Performance",
        "module": "Automation",
        "actions": ["can_view"],
        "description": "Agent metrics and performance tracking"
    },

    # Recruitment Offers
    "offers": {
        "display_name": "Offers",
        "module": "Recruitment",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Job offers and offer management"
    },

    # HR Allocations
    "allocations": {
        "display_name": "Allocations",
        "module": "HR",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Employee project allocations"
    },

    # Finance Additional
    "revenue": {
        "display_name": "Revenue",
        "module": "Finance",
        "actions": ["can_view", "can_edit"],
        "description": "Revenue tracking and management"
    },
    "expenses": {
        "display_name": "Expenses",
        "module": "Finance",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Expense tracking and reimbursement"
    },

    # Dashboards & Reports
    "dashboards": {
        "display_name": "Dashboards",
        "module": "Analytics",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Custom dashboards and widgets"
    },
    "reports": {
        "display_name": "Reports",
        "module": "Analytics",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Business reports and analytics"
    },
    "analytics": {
        "display_name": "Analytics",
        "module": "Analytics",
        "actions": ["can_view", "can_edit"],
        "description": "Analytics and data insights"
    },

    # Configuration & System
    "system_config": {
        "display_name": "System Configuration",
        "module": "Administration",
        "actions": ["can_view", "can_edit"],
        "description": "System settings and configuration"
    },
    "notifications": {
        "display_name": "Notifications",
        "module": "Administration",
        "actions": ["can_view", "can_edit"],
        "description": "Notification settings and preferences"
    },

    # Integrations
    "integrations": {
        "display_name": "Integrations",
        "module": "Administration",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "External system integrations"
    },

    # Business Units
    "business_units": {
        "display_name": "Business Units",
        "module": "Administration",
        "actions": ["can_view", "can_create", "can_edit", "can_delete"],
        "description": "Business unit management"
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

    # Timesheets
    TIMESHEETS_VIEW = ("timesheets", "can_view")
    TIMESHEETS_CREATE = ("timesheets", "can_create")
    TIMESHEETS_EDIT = ("timesheets", "can_edit")
    TIMESHEETS_DELETE = ("timesheets", "can_delete")

    # Invoices
    INVOICES_VIEW = ("invoices", "can_view")
    INVOICES_CREATE = ("invoices", "can_create")
    INVOICES_EDIT = ("invoices", "can_edit")
    INVOICES_DELETE = ("invoices", "can_delete")

    # Opportunities
    OPPORTUNITIES_VIEW = ("opportunities", "can_view")
    OPPORTUNITIES_CREATE = ("opportunities", "can_create")
    OPPORTUNITIES_EDIT = ("opportunities", "can_edit")
    OPPORTUNITIES_DELETE = ("opportunities", "can_delete")

    # Clients
    CLIENTS_VIEW = ("clients", "can_view")
    CLIENTS_CREATE = ("clients", "can_create")
    CLIENTS_EDIT = ("clients", "can_edit")
    CLIENTS_DELETE = ("clients", "can_delete")

    # Business Units
    BUSINESS_UNITS_VIEW = ("business_units", "can_view")
    BUSINESS_UNITS_CREATE = ("business_units", "can_create")
    BUSINESS_UNITS_EDIT = ("business_units", "can_edit")
    BUSINESS_UNITS_DELETE = ("business_units", "can_delete")

    # Users & Administration
    USERS_VIEW = ("users", "can_view")
    USERS_CREATE = ("users", "can_create")
    USERS_EDIT = ("users", "can_edit")
    USERS_DELETE = ("users", "can_delete")

    ROLE_TEMPLATES_VIEW = ("role_templates", "can_view")
    ROLE_TEMPLATES_CREATE = ("role_templates", "can_create")
    ROLE_TEMPLATES_EDIT = ("role_templates", "can_edit")
    ROLE_TEMPLATES_DELETE = ("role_templates", "can_delete")

    # Agents & Automation
    AGENTS_VIEW = ("agents", "can_view")
    AGENTS_CREATE = ("agents", "can_create")
    AGENTS_EDIT = ("agents", "can_edit")
    AGENTS_DELETE = ("agents", "can_delete")

    AGENT_CONFIG_VIEW = ("agent_config", "can_view")
    AGENT_CONFIG_EDIT = ("agent_config", "can_edit")

    AGENT_PERFORMANCE_VIEW = ("agent_performance", "can_view")

    # Offers
    OFFERS_VIEW = ("offers", "can_view")
    OFFERS_CREATE = ("offers", "can_create")
    OFFERS_EDIT = ("offers", "can_edit")
    OFFERS_DELETE = ("offers", "can_delete")

    # Allocations
    ALLOCATIONS_VIEW = ("allocations", "can_view")
    ALLOCATIONS_CREATE = ("allocations", "can_create")
    ALLOCATIONS_EDIT = ("allocations", "can_edit")
    ALLOCATIONS_DELETE = ("allocations", "can_delete")

    # Revenue & Expenses
    REVENUE_VIEW = ("revenue", "can_view")
    REVENUE_EDIT = ("revenue", "can_edit")

    EXPENSES_VIEW = ("expenses", "can_view")
    EXPENSES_CREATE = ("expenses", "can_create")
    EXPENSES_EDIT = ("expenses", "can_edit")
    EXPENSES_DELETE = ("expenses", "can_delete")

    # Dashboards & Reports
    DASHBOARDS_VIEW = ("dashboards", "can_view")
    DASHBOARDS_CREATE = ("dashboards", "can_create")
    DASHBOARDS_EDIT = ("dashboards", "can_edit")
    DASHBOARDS_DELETE = ("dashboards", "can_delete")

    REPORTS_VIEW = ("reports", "can_view")
    REPORTS_CREATE = ("reports", "can_create")
    REPORTS_EDIT = ("reports", "can_edit")
    REPORTS_DELETE = ("reports", "can_delete")

    ANALYTICS_VIEW = ("analytics", "can_view")
    ANALYTICS_EDIT = ("analytics", "can_edit")

    # System Configuration
    SYSTEM_CONFIG_VIEW = ("system_config", "can_view")
    SYSTEM_CONFIG_EDIT = ("system_config", "can_edit")

    NOTIFICATIONS_VIEW = ("notifications", "can_view")
    NOTIFICATIONS_EDIT = ("notifications", "can_edit")

    # Integrations
    INTEGRATIONS_VIEW = ("integrations", "can_view")
    INTEGRATIONS_CREATE = ("integrations", "can_create")
    INTEGRATIONS_EDIT = ("integrations", "can_edit")
    INTEGRATIONS_DELETE = ("integrations", "can_delete")


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
