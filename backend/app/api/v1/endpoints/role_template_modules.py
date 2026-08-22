"""Module and Resource listing endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.models.role_template import Module, Resource

router = APIRouter(prefix="/admin/modules", tags=["Modules & Resources"])


@router.get("")
def list_modules_and_resources(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get all modules with their resources for role template builder."""

    modules = db.query(Module).filter(
        Module.tenant_id == current_user.tenant_id,
        Module.enabled == True
    ).all()

    result = []
    for module in modules:
        resources = db.query(Resource).filter(
            Resource.module_id == module.id,
            Resource.enabled == True
        ).all()

        resource_list = [
            {
                "id": r.id,
                "name": r.name,
                "display_name": r.display_name,
                "route_path": r.route_path,
                "description": r.description,
            }
            for r in resources
        ]

        result.append({
            "id": module.id,
            "name": module.name,
            "display_name": module.display_name,
            "description": module.description,
            "resources": resource_list,
        })

    return {"modules": result}


@router.get("/{module_id}/resources")
def get_module_resources(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get resources for a specific module."""

    module = db.query(Module).filter(
        Module.id == module_id,
        Module.tenant_id == current_user.tenant_id
    ).first()

    if not module:
        return {"error": "Module not found"}, 404

    resources = db.query(Resource).filter(
        Resource.module_id == module.id,
        Resource.enabled == True
    ).all()

    resource_list = [
        {
            "id": r.id,
            "name": r.name,
            "display_name": r.display_name,
            "route_path": r.route_path,
            "description": r.description,
        }
        for r in resources
    ]

    return {
        "module_id": module.id,
        "module_name": module.name,
        "module_display": module.display_name,
        "resources": resource_list,
    }
