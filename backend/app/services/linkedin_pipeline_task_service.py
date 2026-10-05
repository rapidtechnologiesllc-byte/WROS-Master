"""
Follow-up tasks for the LinkedIn candidate pipeline.

Each manual stage has exactly one open task for the item's owner, due
today so it shows on My Tasks. Moving the item to the next stage completes
that task and opens the next one; Imported to Thunder has none.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.models.task import Task
from app.services.task_service import create_task

# Outreach follow-up per stage: who does what next. IMPORTED_TO_THUNDER has
# no manual step -- Thunder takes over.
_STAGE_TASKS = {
    LinkedInPipelineStatus.PENDING_CONNECTION: (
        "LinkedIn: send connection request to {name}",
        "Send a LinkedIn connection request to {url}. When they accept, set the pipeline status to Connected.",
    ),
    LinkedInPipelineStatus.CONNECTED: (
        "LinkedIn: collect phone number from {name}",
        "{name} accepted your connection ({url}). Message them for a phone number, then set the status to Phone Collected.",
    ),
    LinkedInPipelineStatus.PHONE_COLLECTED: (
        "LinkedIn: import {name} to Thunder",
        "Phone collected for {name} ({url}). Import them from the LinkedIn Pipeline screen to start Thunder outreach.",
    ),
}

def sync_outreach_task(db: Session, item: LinkedInCandidatePipeline, tenant_id: Optional[int]) -> None:
    """Close the task for the previous stage and open one for the current
    stage, assigned to the pipeline item's owner and due today (so it lands
    on My Tasks). Caller commits."""
    if item.task_id:
        previous = db.query(Task).filter(Task.id == int(item.task_id)).first()
        if previous and previous.status not in ("COMPLETED", "CANCELLED"):
            previous.status = "COMPLETED"
            previous.completed_at = datetime.utcnow()
            db.add(previous)
        item.task_id = None

    stage = _STAGE_TASKS.get(item.status)
    if stage is None or not item.assigned_to_user_id:
        return
    name = item.linkedin_profile_slug.replace("-", " ").title()
    title, description = (part.format(name=name, url=item.linkedin_url) for part in stage)
    task = create_task(
        db,
        title=title,
        description=description,
        priority="MEDIUM",
        category="LINKEDIN_OUTREACH",
        assigned_to_user_id=item.assigned_to_user_id,
        created_by_user_id=item.assigned_to_user_id,
        due_date=datetime.utcnow(),
        tenant_id=tenant_id,
    )
    item.task_id = str(task.id)
    db.add(item)


def backfill_outreach_tasks(db: Session) -> int:
    """Open a task for in-progress items that have none (items queued before
    tasks existed). Idempotent: items with a task_id are skipped."""
    items = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.task_id.is_(None),
        LinkedInCandidatePipeline.status != LinkedInPipelineStatus.IMPORTED_TO_THUNDER,
        LinkedInCandidatePipeline.assigned_to_user_id.isnot(None),
    ).all()
    from app.models.user import Users

    created = 0
    for item in items:
        owner = db.query(Users).filter(Users.UserID == item.assigned_to_user_id).first()
        if owner is None:
            logger.warning(
                f"[LinkedInPipeline] Skipping task backfill for {item.id}: "
                f"owner {item.assigned_to_user_id!r} no longer exists"
            )
            continue
        sync_outreach_task(db, item, owner.tenant_id)
        created += 1
    if created:
        db.commit()
        logger.info(f"[LinkedInPipeline] Backfilled outreach tasks for {created} item(s)")
    return created
