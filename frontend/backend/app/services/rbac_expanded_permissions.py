"""
Expanded RBAC Permission Model - HubSpot Style (Module × Verb)

Replaces the coarse 28-permission model with a granular per-module, per-verb model.

NOTE: Modules and verbs are now FETCHED FROM DATABASE via ModuleService.
The lists below are SEED DATA and FALLBACKS only - they are used during initial database
setup and as fallback if database queries fail. All production code should use
ModuleService.get_all_modules() and ModuleService.get_verb_matrix() instead.

HARDCODED SEED DATA ONLY (use ModuleService for runtime queries):
"""

# ════════════════════════════════════════════════════════════════════════════
# SEED DATA: Hardcoded module list for database initialization
# DO NOT USE IN CODE - use ModuleService.get_all_modules() instead
# ════════════════════════════════════════════════════════════════════════════

MODULES = [
    # Recruitment
    "candidates",
    "jobs",
    "interviews",
    "offers",
    "submissions",
    "offer_readiness",
    "candidate_review",
    "bulk_launch",
    "thunder_analytics",

    # Sales
    "clients",
    "demand",
    "opportunities",
    "opportunity_pipeline",
    "partner_roi",

    # Project Management / Delivery
    "employees",
    "projects",
    "allocations",
    "resource_management",
    "core_pull",
    "utilization",
    "forecast",
    "buddy_program",
    "htd_intake",

    # Finance & Operations
    "invoices",
    "timesheets",
    "expenses",
    "revenue",
    "forecasting",
    "finance_operations",

    # Admin & Configuration
    "rbac",
    "users",
    "tenant_config",
    "locale",
    "ai_config",
    "message_templates",
    "ticket_routing",
    "documents",
    "reports",
    "tasks",
    "notifications",
    "error_log",
    "admin_settings",
    "executive_signal",
]

# Verbs applicable per module
VERB_MATRIX = {
    # Recruitment
    "candidates": ["view", "create", "edit", "delete", "merge"],
    "jobs": ["view", "create", "edit", "delete"],
    "interviews": ["view", "create", "edit", "delete"],
    "offers": ["view", "create", "edit", "delete", "approve"],
    "submissions": ["view", "create", "edit", "delete"],
    "offer_readiness": ["view"],
    "candidate_review": ["view", "edit"],
    "bulk_launch": ["view", "create"],
    "thunder_analytics": ["view"],

    # Sales
    "clients": ["view", "create", "edit", "delete"],
    "demand": ["view", "create", "edit", "delete"],
    "opportunities": ["view", "create", "edit", "delete"],
    "opportunity_pipeline": ["view", "edit"],
    "partner_roi": ["view"],

    # Project Management / Delivery
    "employees": ["view", "create", "edit", "delete"],
    "projects": ["view", "create", "edit", "delete"],
    "allocations": ["view", "create", "edit", "delete"],
    "resource_management": ["view", "edit"],
    "core_pull": ["view", "edit"],
    "utilization": ["view"],
    "forecast": ["view", "create", "edit"],
    "buddy_program": ["view", "edit"],
    "htd_intake": ["view", "create"],

    # Finance & Operations
    "invoices": ["view", "create", "edit", "approve"],
    "timesheets": ["view", "create", "edit", "approve"],
    "expenses": ["view", "create", "edit", "approve"],
    "revenue": ["view", "view_pnl", "edit"],
    "forecasting": ["view", "create", "edit"],
    "finance_operations": ["view", "edit"],

    # Admin & Configuration
    "rbac": ["view", "manage"],  # manage = full control
    "users": ["view", "create", "edit", "delete"],
    "tenant_config": ["view", "edit"],
    "locale": ["view", "edit"],
    "ai_config": ["view", "edit"],
    "message_templates": ["view", "create", "edit", "delete"],
    "ticket_routing": ["view", "edit"],
    "documents": ["view", "upload", "verify", "delete"],
    "reports": ["view", "create", "edit", "delete"],
    "tasks": ["view", "create", "edit"],
    "notifications": ["view", "edit"],
    "error_log": ["view"],
    "admin_settings": ["view", "edit"],
    "executive_signal": ["view"],
}


def generate_permission_name(module: str, verb: str) -> str:
    """Generate permission name from module and verb: 'candidates.view', 'jobs.create'"""
    return f"{module}.{verb}"


def generate_all_permissions() -> list:
    """Generate all module × verb permissions from VERB_MATRIX"""
    permissions = []
    for module, verbs in VERB_MATRIX.items():
        for verb in verbs:
            perm_name = generate_permission_name(module, verb)
            perm_desc = f"{verb.title()} {module.replace('_', ' ')}"
            permissions.append({
                "name": perm_name,
                "description": perm_desc,
                "module": module,
                "verb": verb
            })
    return permissions


# Role-to-permissions mapping for common roles
ROLE_PERMISSIONS_NEW = {
    "Super User": {
        # Super User has access to everything across all modules
        "candidates": ["view", "create", "edit", "delete", "merge"],
        "jobs": ["view", "create", "edit", "delete"],
        "interviews": ["view", "create", "edit", "delete"],
        "offers": ["view", "create", "edit", "delete", "approve"],
        "submissions": ["view", "create", "edit", "delete"],
        "offer_readiness": ["view"],
        "candidate_review": ["view", "edit"],
        "bulk_launch": ["view", "create"],
        "thunder_analytics": ["view"],
        "clients": ["view", "create", "edit", "delete"],
        "demand": ["view", "create", "edit", "delete"],
        "opportunities": ["view", "create", "edit", "delete"],
        "opportunity_pipeline": ["view", "edit"],
        "partner_roi": ["view"],
        "employees": ["view", "create", "edit", "delete"],
        "projects": ["view", "create", "edit", "delete"],
        "allocations": ["view", "create", "edit", "delete"],
        "resource_management": ["view", "edit"],
        "core_pull": ["view", "edit"],
        "utilization": ["view"],
        "forecast": ["view", "create", "edit"],
        "buddy_program": ["view", "edit"],
        "htd_intake": ["view", "create"],
        "invoices": ["view", "create", "edit", "approve"],
        "timesheets": ["view", "create", "edit", "approve"],
        "expenses": ["view", "create", "edit", "approve"],
        "revenue": ["view", "view_pnl", "edit"],
        "forecasting": ["view", "create", "edit"],
        "finance_operations": ["view", "edit"],
        "rbac": ["view", "manage"],
        "users": ["view", "create", "edit", "delete"],
        "tenant_config": ["view", "edit"],
        "locale": ["view", "edit"],
        "ai_config": ["view", "edit"],
        "message_templates": ["view", "create", "edit", "delete"],
        "ticket_routing": ["view", "edit"],
        "documents": ["view", "upload", "verify", "delete"],
        "reports": ["view", "create", "edit", "delete"],
        "tasks": ["view", "create", "edit"],
        "notifications": ["view", "edit"],
        "error_log": ["view"],
        "admin_settings": ["view", "edit"],
        "executive_signal": ["view"],
    },
    "Partner": {
        "candidates": ["view", "create", "edit", "merge"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create", "edit", "approve"],
        "employees": ["view", "edit"],
        "documents": ["view", "verify"],
        "invoices": ["view"],
        "revenue": ["view", "view_pnl"],
        "opportunities": ["view", "create", "edit"],
        "demand": ["view", "create", "edit"],
        "clients": ["view", "create", "edit"],
        "rbac": ["view"],
        "reports": ["view", "create"],
    },
    "BU Head": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create", "edit"],
        "employees": ["view", "edit"],
        "documents": ["view"],
        "revenue": ["view", "view_pnl"],
        "opportunities": ["view", "create", "edit"],
        "demand": ["view", "create", "edit"],
        "clients": ["view"],
        "reports": ["view", "create"],
    },
    "HR Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create", "edit"],
        "employees": ["view", "create", "edit"],
        "documents": ["view", "upload"],
        "invoices": ["view"],
        "timesheets": ["view", "approve"],
        "expenses": ["view", "approve"],
        "revenue": ["view"],  # no view_pnl per Avinash's rule
        "rbac": ["view"],
        "reports": ["view"],
    },
    "Recruiting Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create"],
        "employees": ["view"],
        "documents": ["view"],
        "invoices": ["view"],
        "reports": ["view"],
    },
    "Hiring Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view"],
        "interviews": ["view", "create"],
        "offers": ["view", "create"],
        "employees": ["view"],
    },
    "Finance": {
        "invoices": ["view", "create", "edit", "approve"],
        "timesheets": ["view", "approve"],
        "expenses": ["view", "approve"],
        "revenue": ["view", "view_pnl"],
        "projects": ["view"],
        "demand": ["view"],
        "reports": ["view", "create"],
    },
    "Employee": {
        "documents": ["view", "upload"],
        "timesheets": ["view", "create", "edit"],
        "expenses": ["view", "create", "edit"],
        "projects": ["view"],
        "reports": ["view"],
    },
    # Organizational Hierarchy Roles (CEO through Senior Consultant)
    "CEO": {
        "candidates": ["view"],
        "jobs": ["view"],
        "invoices": ["view", "view_pnl"],
        "timesheets": ["view", "approve"],
        "expenses": ["view", "approve"],
        "revenue": ["view", "view_pnl"],
        "projects": ["view"],
        "employees": ["view"],
        "rbac": ["view"],
        "reports": ["view", "create"],
        "executive_signal": ["view"],
        "forecasting": ["view"],
        "partner_roi": ["view"],
    },
    "Senior Director": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create", "edit", "approve"],
        "employees": ["view", "edit"],
        "projects": ["view", "edit"],
        "allocations": ["view", "edit"],
        "resource_management": ["view", "edit"],
        "invoices": ["view", "approve"],
        "timesheets": ["view", "approve"],
        "expenses": ["view", "approve"],
        "revenue": ["view", "view_pnl"],
        "reports": ["view", "create"],
    },
    "Director": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "offers": ["view", "create", "edit"],
        "employees": ["view", "edit"],
        "projects": ["view", "create", "edit"],
        "allocations": ["view", "create", "edit"],
        "resource_management": ["view", "edit"],
        "invoices": ["view"],
        "timesheets": ["view", "approve"],
        "expenses": ["view", "approve"],
        "revenue": ["view"],
        "reports": ["view", "create"],
    },
    "Technical Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "employees": ["view", "edit"],
        "projects": ["view", "create", "edit"],
        "allocations": ["view", "create", "edit"],
        "resource_management": ["view", "edit"],
        "timesheets": ["view", "approve"],
        "expenses": ["view"],
        "reports": ["view"],
    },
    "Senior Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create", "edit"],
        "interviews": ["view", "create", "edit"],
        "employees": ["view", "edit"],
        "projects": ["view", "create", "edit"],
        "allocations": ["view", "create", "edit"],
        "timesheets": ["view", "approve"],
        "expenses": ["view"],
        "reports": ["view"],
    },
    "Manager": {
        "candidates": ["view", "create", "edit"],
        "jobs": ["view", "create"],
        "interviews": ["view", "create", "edit"],
        "employees": ["view", "edit"],
        "projects": ["view"],
        "allocations": ["view", "edit"],
        "timesheets": ["view", "approve"],
        "expenses": ["view"],
        "reports": ["view"],
    },
    "Team Lead": {
        "candidates": ["view"],
        "jobs": ["view"],
        "interviews": ["view"],
        "employees": ["view"],
        "projects": ["view"],
        "allocations": ["view"],
        "timesheets": ["view"],
        "reports": ["view"],
    },
    "Senior Consultant": {
        "candidates": ["view"],
        "jobs": ["view"],
        "interviews": ["view"],
        "employees": ["view"],
        "projects": ["view"],
        "timesheets": ["view", "create", "edit"],
        "expenses": ["view", "create", "edit"],
        "documents": ["view", "upload"],
        "reports": ["view"],
    },
}


def get_role_permissions(role_name: str) -> list:
    """Get list of permission names for a given role"""
    if role_name == "Super User":
        # All permissions
        return [p["name"] for p in generate_all_permissions()]

    role_perms = ROLE_PERMISSIONS_NEW.get(role_name, {})
    perms = []
    for module, verbs in role_perms.items():
        for verb in verbs:
            perms.append(generate_permission_name(module, verb))
    return perms


def has_permission(role_name: str, module: str, verb: str) -> bool:
    """Check if a role has permission for a module.verb combination"""
    if role_name == "Super User":
        # Super User has all permissions
        return True

    role_perms = ROLE_PERMISSIONS_NEW.get(role_name, {})
    module_verbs = role_perms.get(module, [])
    return verb in module_verbs


def get_all_role_names() -> list:
    """Get all defined role names"""
    return list(ROLE_PERMISSIONS_NEW.keys())


def get_role_modules(role_name: str) -> list:
    """Get all modules a role has access to"""
    if role_name == "Super User":
        return MODULES

    role_perms = ROLE_PERMISSIONS_NEW.get(role_name, {})
    return list(role_perms.keys())


def get_role_for_org_position(position_title: str) -> str:
    """Map org position title to RBAC role name"""
    position_to_role = {
        "CEO": "CEO",
        "Partner": "Partner",
        "BU Head": "BU Head",
        "Senior Director": "Senior Director",
        "Director": "Director",
        "Technical Manager": "Technical Manager",
        "Senior Manager": "Senior Manager",
        "Manager": "Manager",
        "Team Lead": "Team Lead",
        "Senior Consultant": "Senior Consultant",
    }
    return position_to_role.get(position_title, "Employee")


def validate_permission_exists(module: str, verb: str) -> bool:
    """Validate that a module.verb permission is defined in VERB_MATRIX"""
    if module not in VERB_MATRIX:
        return False
    return verb in VERB_MATRIX.get(module, [])


def get_permissions_by_module(module: str) -> list:
    """Get all permission names for a specific module across all roles"""
    if module not in VERB_MATRIX:
        return []

    perms = []
    for verb in VERB_MATRIX[module]:
        perms.append(generate_permission_name(module, verb))
    return perms


def get_module_description(module: str) -> str:
    """Get a friendly description of a module"""
    descriptions = {
        "candidates": "Candidate Management",
        "jobs": "Job Postings",
        "interviews": "Interview Scheduling",
        "offers": "Offer Management",
        "submissions": "Candidate Submissions",
        "offer_readiness": "Offer Readiness",
        "candidate_review": "Candidate Review",
        "bulk_launch": "Bulk Operations",
        "thunder_analytics": "Thunder Analytics",
        "clients": "Client Management",
        "demand": "Demand Planning",
        "opportunities": "Sales Opportunities",
        "opportunity_pipeline": "Opportunity Pipeline",
        "partner_roi": "Partner ROI",
        "employees": "Employee Management",
        "projects": "Projects",
        "allocations": "Resource Allocations",
        "resource_management": "Resource Management",
        "core_pull": "Core-Pull Decision",
        "utilization": "Utilization Tracking",
        "forecast": "Forecasting",
        "buddy_program": "Buddy Program",
        "htd_intake": "HTD Intake",
        "invoices": "Invoicing",
        "timesheets": "Timesheets",
        "expenses": "Expenses",
        "revenue": "Revenue Tracking",
        "forecasting": "Forecasting",
        "finance_operations": "Finance Operations",
        "rbac": "RBAC Management",
        "users": "User Management",
        "tenant_config": "Tenant Configuration",
        "locale": "Localization",
        "ai_config": "AI Configuration",
        "message_templates": "Message Templates",
        "ticket_routing": "Ticket Routing",
        "documents": "Document Management",
        "reports": "Reports",
        "tasks": "Task Management",
        "notifications": "Notifications",
        "error_log": "Error Logs",
        "admin_settings": "Admin Settings",
        "executive_signal": "Executive Dashboard",
    }
    return descriptions.get(module, module.replace("_", " ").title())


# ════════════════════════════════════════════════════════════════════════════
# DATABASE-DRIVEN MODULE & VERB QUERIES
# These functions query from database and fall back to hardcoded data
# ════════════════════════════════════════════════════════════════════════════

def get_modules_from_db(db) -> list:
    """Get all modules from database, fallback to hardcoded MODULES if database unavailable."""
    try:
        from app.services.module_service import ModuleService
        db_modules = ModuleService.get_module_names(db, tenant_id=1, active_only=True)
        return db_modules if db_modules else MODULES
    except Exception:
        # Fallback to hardcoded data if database query fails
        return MODULES


def get_verb_matrix_from_db(db) -> dict:
    """Get verb matrix from database, fallback to hardcoded VERB_MATRIX if database unavailable."""
    try:
        from app.services.module_service import ModuleService
        db_matrix = ModuleService.get_verb_matrix(db, tenant_id=1)
        return db_matrix if db_matrix else VERB_MATRIX
    except Exception:
        # Fallback to hardcoded data if database query fails
        return VERB_MATRIX
