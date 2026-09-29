"""Create User With Roles Handler - Creates the Users row queued by
POST /hr/users/create-with-roles, together with the user's own seat in the
org chart (an OrgNode under parent_node_id) so the account, its role
template, business unit, department, delivery center and reporting line are
written in one transaction and can't drift apart.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.role_template import RoleTemplate
from app.models.user import Users
from app.services.org_structure_service import create_org_node
from app.utils.uniq_id_generator import user_id_generator

logger = logging.getLogger(__name__)


def handle_create_user_with_roles(message: Any, db: Session) -> Dict[str, Any]:
    payload = message.payload or {}

    user_email = payload.get("user_email")
    user_name = payload.get("user_name")
    user_password = payload.get("user_password")
    role_ids = payload.get("role_ids") or []
    tenant_id = payload.get("tenant_id", 1)

    if not user_email or not user_name or not user_password:
        raise ValueError(
            f"create_user_with_roles payload missing required field(s): "
            f"user_email={bool(user_email)}, user_name={bool(user_name)}, "
            f"user_password={bool(user_password)}"
        )
    if not role_ids:
        raise ValueError("create_user_with_roles payload missing role_ids")

    existing = db.query(Users).filter(Users.UserEmail == user_email).first()
    if existing:
        # Not retryable - the endpoint already checked this before queueing,
        # but the queue can be slower than a second concurrent request.
        raise ValueError(f"User with email {user_email} already exists")

    role_template = db.query(RoleTemplate).filter(RoleTemplate.id == role_ids[0]).first()
    if role_template is None:
        raise ValueError(f"Role template {role_ids[0]} not found")

    try:
        # Re-validated here: the org chart may have changed since the endpoint queued this.
        org_node = create_org_node(
            db,
            tenant_id=tenant_id,
            name=user_name,
            hierarchy_level=payload.get("hierarchy_level") or role_template.hierarchy_level,
            specialization=payload.get("specialization") or role_template.specialization,
            parent_id=payload.get("parent_node_id"),
            department_id=payload.get("department_id"),
        )

        user = Users(
            UserID=user_id_generator(),
            UserEmail=user_email,
            UserName=user_name,
            UserPassword=get_password_hash(user_password),
            UserRole=role_template.name,
            role_template_id=role_template.id,
            business_unit_id=payload.get("business_unit_id"),
            department_id=payload.get("department_id"),
            location_id=payload.get("location_id"),
            org_node_id=org_node.id,
            job_title=payload.get("job_title"),
            tenant_id=tenant_id,
            password_reset_required=True,
        )
        db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        f"[CreateUserWithRoles] Created user {user.UserID} ({user_email}) "
        f"role_template_id={role_template.id} org_node_id={org_node.id} tenant_id={tenant_id}"
    )

    return {
        "status": "user_created",
        "user_id": user.UserID,
        "user_email": user_email,
        "org_node_id": org_node.id,
    }
