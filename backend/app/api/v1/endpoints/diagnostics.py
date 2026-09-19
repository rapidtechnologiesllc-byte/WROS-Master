"""Diagnostic endpoints for troubleshooting system health."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, inspect
from app.core.database import get_db
from app.models.user import Users

router = APIRouter(prefix="/admin/diagnostics", tags=["diagnostics"])


@router.get("/auth-state")
def check_auth_state(db: Session = Depends(get_db)):
    """Check if user records have required fields for RequestContext"""

    try:
        total_users = db.query(func.count(Users.UserID)).scalar() or 0
        users_with_tenant_id = db.query(func.count(Users.UserID)).filter(
            Users.tenant_id.isnot(None)
        ).scalar() or 0
        users_with_role = db.query(func.count(Users.UserID)).filter(
            Users.role_template_id.isnot(None)
        ).scalar() or 0

        # Get list of users missing fields (for debugging)
        missing_tenant = db.query(Users.UserID, Users.UserEmail, Users.tenant_id).filter(
            Users.tenant_id.is_(None)
        ).limit(5).all()

        missing_role = db.query(Users.UserID, Users.UserEmail, Users.role_template_id).filter(
            Users.role_template_id.is_(None)
        ).limit(5).all()

        return {
            "total_users": total_users,
            "users_with_tenant_id": users_with_tenant_id,
            "users_with_role_template_id": users_with_role,
            "missing_tenant_id": max(0, total_users - users_with_tenant_id),
            "missing_role_template_id": max(0, total_users - users_with_role),
            "status": "OK" if (users_with_tenant_id == total_users and users_with_role == total_users) else "PROBLEM",
            "sample_missing_tenant": [{"id": str(u[0]), "email": u[1], "tenant_id": u[2]} for u in missing_tenant],
            "sample_missing_role": [{"id": str(u[0]), "email": u[1], "role_template_id": u[2]} for u in missing_role]
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "ERROR",
            "total_users": 0
        }
