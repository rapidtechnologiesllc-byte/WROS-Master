"""Record a meeting or conversation with a client (CEO 2026-11-02: "allowing to add updates and
overall missing the context of what the meeting got us and where we are heading next").

A ClientUpdate says when, who, what was discussed and what was agreed; each next step becomes a real
task for its owner (task_service.create_task), so "where we are heading next" is work someone owns
with a date, not a line in a note. The update shows on the client's History.
"""
import logging
from datetime import date, datetime, time
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_update import ClientUpdate
from app.models.opportunity import Opportunity
from app.models.user import Users

logger = logging.getLogger(__name__)

CLIENT_MANAGEMENT_LINK = "/client-management"


class ClientUpdateError(ValueError):
    pass


def _owner(db: Session, user_id: str, tenant_id: Optional[int]) -> Users:
    user = db.query(Users).filter(Users.UserID == user_id).first()
    if user is None or (tenant_id is not None and user.tenant_id != tenant_id):
        raise ClientUpdateError(f"Next-step owner {user_id!r} is not a user of this organisation.")
    if user.terminated_at is not None:
        raise ClientUpdateError(f"Next-step owner {user.UserName or user_id} has left the organisation.")
    return user


def record_client_update(db: Session, client: Client, *, actor: Users, meeting_date: date, summary: str,
                         attendees: Optional[str] = None, decisions: Optional[str] = None,
                         opportunity_id: Optional[str] = None,
                         next_steps: Optional[List[Dict]] = None) -> ClientUpdate:
    """Save the update and create one task per next step ({title, owner_user_id, due_date}).
    Everything is validated before the first write; task_service.create_task commits each task
    (and tells its owner), so the update is committed with the first one."""
    from app.services.task_service import create_task

    if not (summary or "").strip():
        raise ClientUpdateError("Say what was discussed.")
    if meeting_date > date.today():
        raise ClientUpdateError("The meeting date cannot be in the future.")
    if opportunity_id:
        opportunity = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if opportunity is None or opportunity.client_id != client.id:
            raise ClientUpdateError("That opportunity is not this client's.")
    steps = []
    for step in next_steps or []:
        title = (step.get("title") or "").strip()
        if not title:
            raise ClientUpdateError("Every next step needs what is to be done.")
        if not step.get("owner_user_id"):
            raise ClientUpdateError(f"Next step {title!r} needs an owner.")
        steps.append((title, _owner(db, step["owner_user_id"], actor.tenant_id), step.get("due_date")))

    update = ClientUpdate(
        tenant_id=client.tenant_id, client_id=client.id, opportunity_id=opportunity_id or None,
        meeting_date=meeting_date, attendees=(attendees or "").strip() or None, summary=summary.strip(),
        decisions=(decisions or "").strip() or None, created_by=actor.UserID,
    )
    db.add(update)
    db.flush()
    task_ids = []
    for title, owner, due in steps:
        task = create_task(
            db, title=f"{client.company_name}: {title}"[:255],
            description=f"Next step from the {meeting_date:%d %b %Y} meeting with {client.company_name}.\n\n"
                        f"{update.summary}",
            created_by_user_id=actor.UserID, assigned_to_user_id=owner.UserID, tenant_id=actor.tenant_id,
            due_date=datetime.combine(due, time(17, 0)) if due else None, task_type="GENERAL",
            category="Client", link=CLIENT_MANAGEMENT_LINK,
        )
        task_ids.append(task.id)
    update.task_ids = task_ids
    logger.info(f"[ClientUpdate] {client.id}: update {update.id} by {actor.UserID}, {len(task_ids)} next step(s)")
    return update
