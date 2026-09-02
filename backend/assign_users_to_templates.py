"""
Database migration script to assign existing users to appropriate role templates.
Run this ONCE to backfill role_template_id on users table.
import logging
"""

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate
from app.core.logging import logger

def assign_users_to_templates():
    """Assign existing users to role templates based on their UserRole field."""
    db = SessionLocal()
    try:
        # Map old UserRole string to new RoleTemplate name
        role_mapping = {
            "Super User": "Super User",
            "Admin": "Admin",
            "Recruiter": "Recruiter",
            "HR Manager": "HR Manager",
            "Hiring Manager": "Hiring Manager",
        }

        # For each user with an old-style role
        users = db.query(Users).filter(Users.UserRole.isnot(None)).all()

        assigned_count = 0
        skipped_count = 0

        for user in users:
            # Check if user already has a role template assigned
            if user.role_template_id:
                skipped_count += 1
                continue

            # Find matching template
            template_name = role_mapping.get(user.UserRole)
            if not template_name:
                logger.warning(f"No template mapping for role: {user.UserRole}")
                continue

            template = db.query(RoleTemplate).filter(
                RoleTemplate.name == template_name,
                RoleTemplate.tenant_id == user.tenant_id
            ).first()

            if not template:
                logger.warning(f"Template not found: {template_name}")
                continue

            # Assign template to user directly (single role per user)
            user.role_template_id = template.id
            db.add(user)
            assigned_count += 1

        db.commit()
        logger.info(f"Migration complete: Assigned {assigned_count} users, Skipped {skipped_count}")
        print(f"✓ Assigned {assigned_count} users to role templates")
        print(f"⊘ Skipped {skipped_count} users (already assigned)")

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        logger.error(f"Migration failed: {e}")
        print(f"✗ Migration failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    assign_users_to_templates()
