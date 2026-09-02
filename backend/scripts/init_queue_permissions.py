#!/usr/bin/env python3
"""Initialize queue-related permissions in role templates."""
import sys
import logging
sys.path.insert(0, '/c/dev/WROS-Master/backend')

from app.core.database import SessionLocal
from app.models.role_template import RoleTemplate
from app.models.permission import Permission

def init_queue_permissions():
    """Add queue-related permissions to existing role templates."""
    db = SessionLocal()
    
    try:
        # Queue-related permissions
        queue_perms = [
            ("message_queue.view", "View message queues"),
            ("message_queue.manage", "Manage message queues"),
            ("candidate.created_event", "Handle candidate creation events"),
            ("interview.scheduled_event", "Handle interview scheduling events"),
            ("offer.generated_event", "Handle offer generation events"),
            ("thunder.autonomous_event", "Handle Thunder autonomous events"),
            ("communication.email_sent", "Handle email sent events"),
        ]

        # Add permissions if they don't exist
        for perm_key, perm_desc in queue_perms:
            existing = db.query(Permission).filter(
                Permission.name == perm_key
            ).first()

            if not existing:
                perm = Permission(
                    name=perm_key,
                    description=perm_desc
                )
                db.add(perm)
                print(f"Added permission: {perm_key}")

        # Assign to roles
        roles_to_update = {
            "Thunder": ["message_queue.view", "message_queue.manage", "thunder.autonomous_event"],
            "Admin": ["message_queue.view", "message_queue.manage"],
            "Recruiter": ["message_queue.view", "candidate.created_event"],
        }

        for role_name, perms in roles_to_update.items():
            role = db.query(RoleTemplate).filter(
                RoleTemplate.name == role_name
            ).first()

            if role:
                for perm_key in perms:
                    perm = db.query(Permission).filter(
                        Permission.name == perm_key
                    ).first()

                    if perm and perm not in role.permissions:
                        role.permissions.append(perm)
                        print(f"Added {perm_key} to {role_name}")

        db.commit()
        print("Queue permissions initialized successfully")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_queue_permissions()
