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
        # Get user ID - handle both Users object and dict formats
        if hasattr(current_user, 'UserID'):
            user_id = current_user.UserID
            tenant_id = getattr(current_user, 'tenant_id', 1)
        else:
            user_id = current_user.get("sub") or current_user.get("user_id")
            tenant_id = current_user.get("tenant_id", 1)

        if not user_id:
            raise HTTPException(status_code=401, detail="User not identified")

        # Get all resources with module relationship
        resources = db.query(Resource).join(Module).filter(
            Resource.tenant_id == tenant_id,
            Resource.enabled == True
        ).all()

        logger.warning(f"[NAV] Building navigation for user_id={user_id}, found {len(resources)} resources")

        # Check permissions for each resource and group by module
        navigation_modules = {}

        for resource in resources:
            # Check if user can view this resource
            can_view = RoleTemplatePermissionService.can_view(
                db, user_id, resource.name, tenant_id
            )

            if can_view:
                # Use module object (already loaded via join)
                module = resource.module
                module_name = module.name
                module_label = module.display_name

                # Initialize module if needed
                if module_name not in navigation_modules:
                    # Get icon for module (use first resource's icon as fallback)
                    module_icon = "Briefcase"
                    if module_name == "Recruitment":
                        module_icon = "Users"
                    elif module_name == "Workforce":
                        module_icon = "Users2"
                    elif module_name == "Finance":
                        module_icon = "BadgeDollarSign"
                    elif module_name == "Admin":
                        module_icon = "Shield"
                    elif module_name == "System":
                        module_icon = "Home"
                    elif module_name == "Executive":
                        module_icon = "TrendingUp"
                    elif module_name == "Engagement":
                        module_icon = "MessageCircle"

                    navigation_modules[module_name] = {
                        "label": module_label,
                        "icon": module_icon,
                        "items": []
                    }

                # Add resource to module (use database fields directly)
                # Generate route if not in database: resource_name -> /resource-name
                route = resource.route_path or f"/{resource.name.replace('_', '-')}"
                navigation_modules[module_name]["items"].append({
                    "key": resource.name,
                    "label": resource.display_name,
                    "icon": get_icon_for_resource(resource.name),
                    "route": route
                })

        # Convert to list of groups
        groups = list(navigation_modules.values())

        logger.warning(f"[NAV] Returning {len(groups)} modules for user_id={user_id}")
        return {"groups": groups}

    except Exception as e:
        logger.error(f"Error building navigation for user {current_user}: {e}", exc_info=True)
        return {"groups": []}
