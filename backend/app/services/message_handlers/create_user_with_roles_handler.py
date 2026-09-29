"""Create User With Roles Handler - Creates the Users row queued by
POST /hr/users/create-with-roles.

The endpoint already validates the org-reporting structure (hierarchy_level,
specialization, parent_node_id) via OrgHierarchyValidator before queueing -
this handler's job is just to actually create the account. hierarchy_level/
specialization/parent_node_id have nowhere to persist on Users itself (no
such columns exist), so this handler creates the login account and role
assignment; linking the new user into an OrgNode for org-chart purposes is
a separate, not-yet-built feature (there's no verified mapping from the
17-level hierarchy scale used here to OrgPosition's separate 10-rank scale
to safely invent one).
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import Users
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

    user = Users(
        UserID=user_id_generator(),
        UserEmail=user_email,
        UserName=user_name,
        UserPassword=get_password_hash(user_password),
        UserRole="User",  # legacy field - role_template_id is the real RBAC assignment
        role_template_id=role_ids[0],
        business_unit_id=payload.get("business_unit_id"),
        department_id=payload.get("department_id"),
        job_title=payload.get("job_title"),
        tenant_id=tenant_id,
        password_reset_required=True,
    )
    db.add(user)
    db.commit()

    logger.info(
        f"[CreateUserWithRoles] Created user {user.UserID} ({user_email}) "
        f"role_template_id={role_ids[0]} tenant_id={tenant_id}"
    )

    return {
        "status": "user_created",
        "user_id": user.UserID,
        "user_email": user_email,
    }
