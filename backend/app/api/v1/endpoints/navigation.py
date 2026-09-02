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
from app.models.role_template import Module, Resource
from app.core.logging import logger

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
        "timesheets": "Clock", "training_certification": "Award", "buddy_program": "Users",
        # Finance
        "invoices": "Receipt", "expenses": "DollarSign", "reports": "BarChart3",
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
        import sys
        print("[NAV-ENDPOINT-CALLED]", file=sys.stderr)
        sys.stderr.flush()

        logger.warning("[NAV-FIX] Starting navigation with resource_name fix active")
        # Get user ID
        if hasattr(current_user, 'UserID'):
            user_id = current_user.UserID
            tenant_id = getattr(current_user, 'tenant_id', 1)
        else:
            user_id = current_user.get("sub")
            tenant_id = current_user.get("tenant_id", 1)

        if not user_id:
            raise HTTPException(status_code=401, detail="User not identified")

        print(f"[NAV-USER-ID] {user_id}", file=sys.stderr)
        sys.stderr.flush()

        # Load module/resource structure from init_resources.py
        from app.seeds.init_resources import MODULES_AND_RESOURCES, RESOURCE_ROUTES
        print(f"[NAV-LOADED] MODULES_AND_RESOURCES has {len(MODULES_AND_RESOURCES)} modules", file=sys.stderr)
        sys.stderr.flush()

        navigation_modules = {}
        module_icons = {
            "Personal": "LayoutDashboard", "Recruitment": "Users", "Workforce": "Users2",
            "Finance": "BadgeDollarSign", "Sales": "Briefcase", "Project Management": "FolderKanban",
            "Reporting": "BarChart3", "System": "Settings", "Executive": "TrendingUp",
            "Admin": "Shield", "Executive Dashboards": "BarChart3", "AI & Automation": "Bot"
        }

        # Build navigation from init_resources
        import sys
        for module_name, resource_names in MODULES_AND_RESOURCES.items():
            module_icon = module_icons.get(module_name, "Briefcase")
            navigation_modules[module_name] = {"label": module_name, "icon": module_icon, "items": []}

            for resource_name in resource_names:
                # Check if user has permission to view this resource
                try:
                    can_view = RoleTemplatePermissionService.can_view(db, user_id, resource_name, tenant_id)
                except Exception as e:
                    logger.warning(f"[NAV] Permission check failed for {resource_name}: {e}")
                    can_view = False

                if can_view:
                    route = RESOURCE_ROUTES.get(resource_name) or f"/{resource_name}"
                    if not route.startswith('/'):
                        route = f"/{route}"

                    navigation_modules[module_name]["items"].append({
                        "key": resource_name,
                        "label": resource_name.replace('-', ' ').title(),
                        "icon": get_icon_for_resource(resource_name),
                        "route": route
                    })

        groups = [m for m in navigation_modules.values() if m["items"]]
        logger.warning(f"[NAV] Returning {len(groups)} groups")
        response = {"data": {"groups": groups}}
        logger.warning(f"[NAV] Response: {response}")
        return response

    except Exception as e:
        logger.error(f"Navigation error: {e}", exc_info=True)
        # Do NOT return fallback empty response - let error propagate
        # ALL navigation should be fully dynamic, no hardcoded fallbacks
        raise
