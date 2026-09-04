"""
import logging
Navigation API - Returns personalized navigation structure based on user permissions.

Endpoint: GET /hr/me/navigation
Returns: Navigation groups with items filtered by user's actual role template permissions.

Uses database resources directly (no hardcoding) - supports all 175 resources dynamically.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_resource_permission
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

@router.get(
    "/navigation",
    dependencies=[Depends(require_resource_permission("navigation", "view"))]
)
def get_user_navigation(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get personalized navigation structure for the logged-in user.

    FULLY DYNAMIC: Returns only resources the user has permission to access,
    grouped by their module, based on actual role template permissions.

    No hardcoding - everything comes from database:
    - Modules from module table
    - Resources from resource table
    - Permissions from role_template_permissions table

    Includes: can_view, can_edit, can_create, can_delete for each resource

    Response format:
    {
        "groups": [
            {
                "label": "Recruitment",
                "icon": "TrendingUp",
                "items": [
                    {
                        "key": "candidates",
                        "label": "Candidates",
                        "icon": "Users",
                        "route": "/candidates",
                        "can_view": true,
                        "can_create": true,
                        "can_edit": true,
                        "can_delete": true
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    try:
        # Get user ID and tenant
        if hasattr(current_user, 'UserID'):
            user_id = current_user.UserID
            tenant_id = getattr(current_user, 'tenant_id', None)
            if tenant_id is None:
                tenant_id = 1  # Default tenant
        else:
            user_id = current_user.get("sub")
            tenant_id = current_user.get("tenant_id", None)
            if tenant_id is None:
                tenant_id = 1  # Default tenant

        if not user_id:
            raise HTTPException(status_code=401, detail="User not identified")
        if not isinstance(tenant_id, int) or tenant_id <= 0:
            raise HTTPException(status_code=400, detail="Invalid tenant ID")

        # MANDATORY: Get user's role template(s) - user MUST have roles
        try:
            from app.models.user import UserRole
            user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
            if not user_roles:
                raise HTTPException(status_code=403, detail="User has no roles assigned - access denied")

            role_template_ids = [ur.role_template_id for ur in user_roles]
            if not role_template_ids:
                raise HTTPException(status_code=403, detail="User roles invalid - access denied")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading user roles: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load user roles")

        # Query ALL modules from database (no hardcoding)
        try:
            modules = db.query(Module).filter(Module.tenant_id == tenant_id).all()
            if not modules:
                logger.warning(f"No modules found for tenant {tenant_id}")
                return {"data": {"groups": []}}
        except Exception as e:
            logger.error(f"Error loading modules: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load modules")

        navigation_modules = {}

        # Build navigation from database resources
        if modules:
            for module in modules:
                # Get all resources in this module
                try:
                    resources = db.query(Resource).filter(Resource.module_id == module.id).all()
                    if not resources or len(resources) == 0:
                        continue
                except Exception as e:
                    logger.error(f"Error loading resources for module {module.id}: {e}", exc_info=True)
                    continue

                # Filter resources by user's permissions
                accessible_items = []
                if resources:  # Validate resources exists before looping
                    for resource in resources:
                        try:
                            # Get user's permissions for this resource (from any of their role templates)
                            perms = db.query(RoleTemplatePermission).filter(
                                RoleTemplatePermission.resource_id == resource.id,
                                RoleTemplatePermission.role_template_id.in_(role_template_ids)
                            ).all()

                            # If user has ANY permission through ANY role, include it
                            if perms and len(perms) > 0:
                                # Merge permissions from all roles (OR logic)
                                can_view = any(p.can_view for p in perms)
                                can_create = any(p.can_create for p in perms)
                                can_edit = any(p.can_edit for p in perms)
                                can_delete = any(p.can_delete for p in perms)

                                # Only include if user has at least one permission
                                if can_view or can_create or can_edit or can_delete:
                                    # Convert resource name to route (kebab-case to path)
                                    route = f"/{resource.name.replace('_', '-')}"
                                    if resource.route_path:
                                        route = resource.route_path

                                    accessible_items.append({
                                        "key": resource.name,
                                        "label": resource.display_name,
                                        "icon": get_icon_for_resource(resource.name),
                                        "route": route,
                                        "can_view": can_view,
                                        "can_create": can_create,
                                        "can_edit": can_edit,
                                        "can_delete": can_delete,
                                    })
                        except Exception as e:
                            logger.error(f"Error processing resource {resource.id}: {e}", exc_info=True)
                            continue

                # Only include module if it has accessible resources
                if accessible_items:
                    navigation_modules[module.id] = {
                        "label": module.display_name,
                        "icon": module.name,  # Use module name as icon key
                        "items": accessible_items
                    }

        # Return only modules with accessible items
        groups = list(navigation_modules.values())
        logger.info(f"[NAV] User {user_id} has access to {len(groups)} modules with {sum(len(m['items']) for m in groups)} total resources")

        return {"data": {"groups": groups}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Navigation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Navigation error: {str(e)}")
