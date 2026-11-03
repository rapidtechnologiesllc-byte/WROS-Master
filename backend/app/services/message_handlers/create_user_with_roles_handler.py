"""Create User With Roles Handler - Creates the Users row queued by
POST /hr/users/create-with-roles, together with the user's own seat in the
org chart (an OrgNode under parent_node_id) so the account, its role
template, business unit, department, delivery center and reporting line are
written in one transaction and can't drift apart.
"""
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.user import Users
from app.services.org_structure_service import create_org_node
from app.utils.uniq_id_generator import user_id_generator
from app.services.account_activation_service import prepare_new_account, queue_account_email

logger = logging.getLogger(__name__)


# Queue handler SLA (gate rule: every handler declares its timeout)
TIMEOUT_SECONDS = 30


def handle_create_user_with_roles(message: Any, db: Session) -> Dict[str, Any]:
    payload = message.payload or {}

    user_email = payload.get("user_email")
    user_name = payload.get("user_name")
    role_ids = payload.get("role_ids") or []
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise ValueError("create_user_with_roles payload missing tenant_id")

    if not user_email or not user_name:
        raise ValueError(
            f"create_user_with_roles payload missing required field(s): "
            f"user_email={bool(user_email)}, user_name={bool(user_name)}"
        )
    if not role_ids:
        raise ValueError("create_user_with_roles payload missing role_ids")

    existing = db.query(Users).filter(Users.UserEmail == user_email).first()
    if existing:
        # Not retryable - the endpoint already checked this before queueing,
        # but the queue can be slower than a second concurrent request.
        raise ValueError(f"User with email {user_email} already exists")

    # Re-validated here: the template may have changed since the endpoint queued this
    from app.services.role_template_permission_service import validate_addon_template
    role_template = validate_addon_template(db, role_ids[0], tenant_id)

    try:
        # Re-validated here: the org chart may have changed since the endpoint queued this.
        org_node = create_org_node(
            db,
            tenant_id=tenant_id,
            name=user_name,
            # Level from the Job Title's role (set by the endpoint); function from the department
            hierarchy_level=payload.get("hierarchy_level") or role_template.hierarchy_level,
            specialization=None,
            parent_id=payload.get("parent_node_id"),
            department_id=payload.get("department_id"),
            # The seat carries the user's company (BX-US / BX-IN)
            company_id=payload.get("location_id"),
        )

        user = Users(
            UserID=user_id_generator(),
            UserEmail=user_email,
            UserName=user_name,
            UserRole=role_template.name,
            role_template_id=role_template.id,
            business_unit_id=payload.get("business_unit_id"),
            department_id=payload.get("department_id"),
            location_id=payload.get("location_id"),
            org_node_id=org_node.id,
            job_title=payload.get("job_title"),
            tenant_id=tenant_id,
        )
        # No password is typed by an admin or emailed (CEO 2026-11-03): the person sets their own from
        # a single-use link, then is asked to connect Outlook (account_activation_service)
        prepare_new_account(db, user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        f"[CreateUserWithRoles] Created user {user.UserID} ({user_email}) "
        f"role_template_id={role_template.id} org_node_id={org_node.id} tenant_id={tenant_id}"
    )

    # The set-your-password email: once per created account (the activation link is made when it is sent)
    welcome_email = "queued" if queue_account_email(user, "ACTIVATE", once_key="created") else "already_queued"

    return {
        "status": "user_created",
        "user_id": user.UserID,
        "user_email": user_email,
        "org_node_id": org_node.id,
        "welcome_email": welcome_email,
    }
