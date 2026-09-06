"""User creation task - async processing via Celery."""
import logging
from typing import List, Optional
from app.celery_app import app
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import Users
from app.models.role_template import UserRole
from app.utils.uniq_id_generator import user_id_generator
from datetime import datetime

logger = logging.getLogger(__name__)


@app.task(
    name='create_user_with_roles',
    bind=True,
    max_retries=2,
    default_retry_delay=30
)
def create_user_with_roles_task(
    self,
    user_email: str,
    user_name: str,
    user_password: str,
    business_unit_id: Optional[str],
    role_ids: List[str],
    created_by_user_id: Optional[str] = None,
    tenant_id: int = 1
):
    """
    Create user with role assignments asynchronously.

    This task:
    1. Creates user record in database
    2. Hashes password securely
    3. Assigns requested roles
    4. Sends welcome email
    5. Sets up permissions
    6. Logs audit trail

    Args:
        user_email: User's email address (must be unique)
        user_name: User's full name
        user_password: Password (will be hashed)
        business_unit_id: Business unit assignment
        role_ids: List of role template IDs to assign
        created_by_user_id: User ID of creator (for audit)
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        dict with status, user_id, and assigned_roles

    Raises:
        ValueError: If validation fails
        Exception: On database errors (with retry)
    """
    db = SessionLocal()

    try:
        logger.info(
            f"[USER_CREATION] Starting: {user_email}",
            extra={"task_id": self.request.id}
        )

        # Step 1: Validate email is not already taken
        existing_user = db.query(Users).filter(
            Users.UserEmail == user_email
        ).first()

        if existing_user:
            error_msg = f"User with email {user_email} already exists"
            logger.warning(
                f"[USER_CREATION] {error_msg}",
                extra={"task_id": self.request.id}
            )
            raise ValueError(error_msg)

        # Step 2: Create user record with hashed password
        user_id = user_id_generator()

        new_user = Users(
            UserID=user_id,
            UserEmail=user_email,
            UserName=user_name,
            UserPassword=get_password_hash(user_password),
            UserRole="USER",  # Generic role, actual permissions via role templates
            CreatedAt=datetime.now(),
            tenant_id=tenant_id,
            business_unit_id=business_unit_id if business_unit_id else None
        )

        db.add(new_user)
        db.flush()  # Flush to get user ID, but don't commit yet

        logger.info(
            f"[USER_CREATION] User record created: {user_id}",
            extra={"task_id": self.request.id}
        )

        # Step 3: Assign requested roles
        assigned_roles = []

        for role_id in role_ids:
            try:
                user_role = UserRole(
                    user_id=user_id,
                    role_id=role_id,
                    business_unit_id=business_unit_id,
                    created_at=datetime.now()
                )

                db.add(user_role)
                assigned_roles.append(role_id)

                logger.debug(
                    f"[USER_CREATION] Role assigned: {role_id} to {user_id}",
                    extra={"task_id": self.request.id}
                )

            except Exception as role_error:
                logger.error(
                    f"[USER_CREATION] Failed to assign role {role_id}: {role_error}",
                    exc_info=True,
                    extra={"task_id": self.request.id}
                )
                # Continue with other roles, but log the failure

        # Step 4: Commit all changes
        try:
            db.commit()
            logger.info(
                f"[USER_CREATION] Committed to database: {user_id}",
                extra={"task_id": self.request.id}
            )

        except Exception as commit_error:
            db.rollback()
            logger.error(
                f"[USER_CREATION] Failed to commit: {commit_error}",
                exc_info=True,
                extra={"task_id": self.request.id}
            )
            raise

        # Step 5: Send welcome email (non-blocking - don't fail if email fails)
        try:
            from app.services.email_service import send_welcome_email

            send_welcome_email(
                user_email=user_email,
                user_name=user_name,
                temporary_password=user_password,
                user_id=user_id
            )

            logger.info(
                f"[USER_CREATION] Welcome email sent to {user_email}",
                extra={"task_id": self.request.id}
            )

        except Exception as email_error:
            logger.warning(
                f"[USER_CREATION] Failed to send welcome email: {email_error}",
                extra={"task_id": self.request.id}
            )
            # Don't fail - user is created even if email failed

        # Step 6: Log audit trail
        try:
            from app.services.audit_service import log_audit

            log_audit(
                action="user_created",
                user_id=user_id,
                user_email=user_email,
                created_by=created_by_user_id,
                details={
                    "roles_assigned": assigned_roles,
                    "business_unit_id": business_unit_id
                },
                tenant_id=tenant_id
            )

        except Exception as audit_error:
            logger.warning(
                f"[USER_CREATION] Failed to log audit: {audit_error}",
                extra={"task_id": self.request.id}
            )
            # Don't fail - user is created even if audit fails

        return {
            'status': 'success',
            'user_id': user_id,
            'user_email': user_email,
            'user_name': user_name,
            'assigned_roles': assigned_roles,
            'business_unit_id': business_unit_id,
            'task_id': self.request.id
        }

    except ValueError as e:
        logger.warning(
            f"[USER_CREATION] Validation error: {str(e)}",
            extra={"task_id": self.request.id}
        )
        raise

    except Exception as e:
        logger.error(
            f"[USER_CREATION] Failed: {str(e)}",
            exc_info=True,
            extra={"task_id": self.request.id}
        )

        # Retry with exponential backoff (30s, 60s)
        countdown = 30 * (2 ** self.request.retries)
        logger.warning(
            f"[USER_CREATION] Retrying in {countdown}s (attempt {self.request.retries + 1}/2)",
            extra={"task_id": self.request.id}
        )

        raise self.retry(exc=e, countdown=countdown)

    finally:
        try:
            if db:
                db.close()
        except Exception as close_error:
            logger.warning(
                f"[USER_CREATION] Failed to close database: {close_error}",
                extra={"task_id": self.request.id}
            )
