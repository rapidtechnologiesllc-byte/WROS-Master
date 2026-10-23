"""
Navigation API - Returns personalized navigation structure based on user permissions.

Endpoint: GET /hr/me/navigation
Returns: Navigation groups with items filtered by user's actual role template permissions.

Uses database resources directly (no hardcoding) - supports all 175 resources dynamically.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.role_template_permission_service import RoleTemplatePermissionService
from app.core.logging import logger
from app.core.tenant_context import tenant_id_of

router = APIRouter(prefix="/hr/me", tags=["navigation"])

def get_icon_for_resource(resource_name: str) -> str:
    """Simple icon mapping for resource names."""
    icon_map = {
        # Recruitment
        "candidates": "Users", "jobs": "Briefcase", "interviews": "Video",
        "offers": "FileText", "hm_candidate_review": "Eye", "interview_schedule": "Calendar",
        "interview_feedback": "MessageSquare", "offer_approve": "CheckCircle",
        # Workforce
        "employees": "Users2", "allocations": "BarChart2", "projects": "FolderOpen",
        "timesheets": "Clock", "buddy_program": "Users",
        # Finance
        "invoices": "Receipt", "expenses": "DollarSign",
        "timesheets": "Clock", "revenue": "TrendingUp", "finance_operations": "Settings",
        # Admin
        "users": "Shield", "roles": "Lock", "role_templates": "Settings",
        "business_units": "Building", "audit_log": "FileText", "error_log": "AlertCircle",
        "message_queue": "MessageSquare", "certifications": "Award",
        # System/Common
        "dashboard": "Home", "profile": "User", "notifications": "Bell",
        "my_tasks": "CheckSquare", "my_timesheet": "Clock", "my_expenses": "DollarSign",
        "my_referrals": "Share2", "thunder": "MessageCircle", "search": "Search",
        # Executive
        "ceo_dashboard": "TrendingUp", "cfo_dashboard": "BarChart3",
        # Engagement
        "thunder_chat": "MessageCircle", "documents": "File", "tasks": "CheckSquare",
        # SLM (Self-Learning Model)
        "slm_dashboard": "Zap", "slm_training_data": "Database",
        "linkedin-pipeline": "Linkedin",
    }
    return icon_map.get(resource_name, "Briefcase")

@router.get("/navigation")
def get_user_navigation(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get personalized navigation structure for the logged-in user.

    Returns only modules and resources the user has permission to access,
    based on their actual role template permissions.

    Uses database fields directly (no hardcoding) - supports all 175 resources.

    Response format:
    {
        "groups": [
            {
                "label": "Recruitment",
                "icon": "Users",
                "items": [
                    {"key": "candidates", "label": "Candidates", "icon": "Users", "route": "/candidates"},
                    ...
                ]
            },
            ...
        ]
    }
    """
    try:
        # Get user ID
        if hasattr(current_user, 'UserID'):
            user_id = current_user.UserID
            tenant_id = tenant_id_of(current_user)
        else:
            user_id = current_user.get("sub")
            tenant_id = current_user.get("tenant_id")
            if tenant_id is None:
                raise HTTPException(status_code=403, detail="User is not assigned to a tenant")

        if not user_id:
            raise HTTPException(status_code=401, detail="User not identified")

        # Module/resource order from the contract; routes and labels from init_resources
        from app.seeds.init_resources import (MODULES_AND_RESOURCES, NAV_LABELS, NAV_TAB_RESOURCES,
                                             RESOURCE_EXTRA_PAGES, RESOURCE_ROUTES)

        from app.contracts import MODULE_ICONS

        navigation_modules = {}

        # The dashboard that is this user's Home ("/") is not listed again under its own name
        from app.core import authority
        home_resource = authority.home_resource(db, current_user) if hasattr(current_user, 'UserID') else None

        # OPTIMIZATION: Batch load all user permissions ONCE (not per-resource)
        all_permissions = RoleTemplatePermissionService.get_user_permissions(db, user_id, tenant_id)


        # Build navigation from init_resources. Only resources with a page
        # (RESOURCE_ROUTES) become menu items; the rest are permission-only.
        # Each page appears once, under the first module that lists it.
        seen_routes = set()
        for module_name, resource_names in MODULES_AND_RESOURCES.items():
            module_icon = MODULE_ICONS.get(module_name, "Briefcase")
            navigation_modules[module_name] = {"label": module_name, "icon": module_icon, "items": []}

            for resource_name in resource_names:
                route = None if resource_name in NAV_TAB_RESOURCES else RESOURCE_ROUTES.get(resource_name)
                if not route or route in seen_routes or resource_name == home_resource:
                    continue

                # The role's permission matrix decides, for every role (no super-user bypass).
                # all_permissions is keyed by the resource's real (hyphenated) name.
                can_view = all_permissions.get(resource_name, {}).get("can_view", False)

                if can_view:
                    seen_routes.add(route)
                    navigation_modules[module_name]["items"].append({
                        "key": resource_name,
                        "label": NAV_LABELS.get(resource_name) or resource_name.replace('-', ' ').title(),
                        "icon": get_icon_for_resource(resource_name),
                        "route": route
                    })
                    for page in RESOURCE_EXTRA_PAGES.get(resource_name, []):
                        if page["route"] in seen_routes:
                            continue
                        seen_routes.add(page["route"])
                        navigation_modules[module_name]["items"].append({
                            "key": page["key"], "label": page["label"],
                            "icon": get_icon_for_resource(page["key"]), "route": page["route"],
                        })

        groups = [m for m in navigation_modules.values() if m["items"]]
        return {"data": {"groups": groups}}

    except Exception as e:
        logger.error(f"Navigation error: {e}", exc_info=True)
        # Do NOT return fallback empty response - let error propagate
        # ALL navigation should be fully dynamic, no hardcoded fallbacks
        raise
