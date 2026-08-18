"""
Navigation API - Returns personalized navigation structure based on user permissions.

Endpoint: GET /hr/me/navigation
Returns: Navigation groups with items filtered by user's actual role template permissions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.role_template_permission_service import RoleTemplatePermissionService
from app.models.role_template import Module, Resource
from app.core.logging import logger

router = APIRouter(prefix="/hr/me", tags=["navigation"])


# Mapping of resource names to nav keys and display info
RESOURCE_NAV_MAP = {
    "candidates": {
        "key": "candidates",
        "label": "Candidates",
        "icon": "Users",
        "module": "Recruitment"
    },
    "jobs": {
        "key": "jobs",
        "label": "Jobs",
        "icon": "Briefcase",
        "module": "Recruitment"
    },
    "interviews": {
        "key": "interviews",
        "label": "Interviews",
        "icon": "Video",
        "module": "Recruitment"
    },
    "offers": {
        "key": "offers",
        "label": "Offers",
        "icon": "FileText",
        "module": "Recruitment"
    },
    "employees": {
        "key": "employees",
        "label": "Employees",
        "icon": "Users2",
        "module": "Workforce"
    },
    "timesheets": {
        "key": "timesheets",
        "label": "Timesheets",
        "icon": "Clock",
        "module": "Workforce"
    },
    "invoices": {
        "key": "invoices",
        "label": "Invoices",
        "icon": "Receipt",
        "module": "Finance"
    },
    "reports": {
        "key": "reports",
        "label": "Reports",
        "icon": "BarChart3",
        "module": "Finance"
    },
    "users": {
        "key": "users",
        "label": "Users",
        "icon": "Shield",
        "module": "Admin"
    },
}

# Module display info
MODULE_INFO = {
    "Recruitment": {
        "label": "Recruitment",
        "icon": "Users"
    },
    "Workforce": {
        "label": "Workforce",
        "icon": "Users2"
    },
    "Finance": {
        "label": "Finance",
        "icon": "BadgeDollarSign"
    },
    "Admin": {
        "label": "Admin",
        "icon": "Shield"
    }
}


@router.get("/navigation")
def get_user_navigation(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Get personalized navigation structure for the logged-in user.

    Returns only modules and resources the user has permission to access,
    based on their actual role template permissions.

    Response format:
    {
        "groups": [
            {
                "label": "Recruitment",
                "icon": "Users",
                "items": [
                    {"key": "candidates", "label": "Candidates", "icon": "Users"},
                    ...
                ]
            },
            ...
        ]
    }
    """
    try:
        user_id = current_user.get("sub") or current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not identified")

        # Get user's tenant ID (default to 1)
        tenant_id = current_user.get("tenant_id", 1)

        # Get all resources
        resources = db.query(Resource).filter(
            Resource.tenant_id == tenant_id,
            Resource.enabled == True
        ).all()

        # Check permissions for each resource and group by module
        navigation_modules = {}

        for resource in resources:
            # Check if user can view this resource
            can_view = RoleTemplatePermissionService.can_view(
                db, user_id, resource.name, tenant_id
            )

            if can_view:
                # Get resource info from mapping
                nav_info = RESOURCE_NAV_MAP.get(resource.name)
                if nav_info:
                    module_name = nav_info["module"]

                    # Initialize module if needed
                    if module_name not in navigation_modules:
                        module_info = MODULE_INFO.get(module_name, {})
                        navigation_modules[module_name] = {
                            "label": module_info.get("label", module_name),
                            "icon": module_info.get("icon", "Briefcase"),
                            "items": []
                        }

                    # Add resource to module
                    navigation_modules[module_name]["items"].append({
                        "key": nav_info["key"],
                        "label": nav_info["label"],
                        "icon": nav_info.get("icon", "Briefcase")
                    })

        # Convert to list of groups
        groups = []
        for module_name, module_data in navigation_modules.items():
            groups.append({
                "label": module_data["label"],
                "icon": module_data["icon"],
                "items": module_data["items"]
            })

        return {
            "groups": groups
        }

    except Exception as e:
        logger.error(f"Error building navigation for user {current_user}: {e}")
        # Return empty navigation on error rather than failing
        return {"groups": []}
