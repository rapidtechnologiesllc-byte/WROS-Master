"""
Expanded RBAC Permission Model - HubSpot Style (Module × Verb)

Replaces the coarse 28-permission model with a granular per-module, per-verb model.
This file defines:
1. The module list
2. The applicable verbs per module
3. The new permission names
4. Role-to-permissions mapping for common roles
"""

# Modules in the system - organized by functional area
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
    "Super User": [
        # All permissions - computed from VERB_MATRIX
    ],
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
