"""
LinkedIn candidate pipeline: candidate creation + follow-up tasks.

Every pipeline item gets a candidate (created through the candidate queue,
Thunder off until Import) and exactly one open follow-up task for its
owner, due today so it shows on My Tasks. Moving the item to the next stage
completes that task and opens the next one; Imported to Thunder has none.
"""
from app.core.tenant_context import sole_tenant_id
import hashlib
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.models.task import Task
from app.services.task_service import create_task

# Candidate email is required and unique; until the recruiter collects the
# real one, a LinkedIn-sourced candidate carries this internal placeholder.
PLACEHOLDER_EMAIL_DOMAIN = "linkedin-pending.blitzenx.com"
CANDIDATE_SOURCE = "linkedin_pipeline"
_BACKFILL_LOCK_KEY = 74210001  # pg advisory lock: one startup backfill at a time

# Outreach follow-up per stage: who does what next. IMPORTED_TO_THUNDER has
# no manual step -- Thunder takes over.
_STAGE_TASKS = {
    LinkedInPipelineStatus.PENDING_CONNECTION: (
        "LinkedIn: send connection request to {name}",
        "Send a LinkedIn connection request to {url}. When they accept, set the pipeline status to Connected.",
    ),
    LinkedInPipelineStatus.CONNECTED: (
        "LinkedIn: collect phone number and email from {name}",
        "{name} accepted your connection ({url}). Message them for a phone number and email, then set the status to Phone Collected.",
    ),
    LinkedInPipelineStatus.PHONE_COLLECTED: (
        "LinkedIn: import {name} to Thunder",
        "Phone collected for {name} ({url}). Import them from the LinkedIn Pipeline screen to start Thunder outreach.",
    ),
}

def placeholder_email(profile_slug: str) -> str:
    """Generate unique placeholder email from LinkedIn profile slug.

    Uses SHA256 hash of the full profile slug to ensure uniqueness,
    even for similar profiles (john-doe-1a2b3c vs john_doe_1a2b3c).
    """
    # Hash the full profile slug to ensure uniqueness
    slug_hash = hashlib.sha256(profile_slug.encode()).hexdigest()[:16]
    return f"li-{slug_hash}@{PLACEHOLDER_EMAIL_DOMAIN}"

def is_placeholder_email(email: Optional[str]) -> bool:
    return bool(email) and email.endswith("@" + PLACEHOLDER_EMAIL_DOMAIN)

def name_from_slug(profile_slug: str):
    """Best guess from the slug, dropping LinkedIn's trailing id (jane-doe-1a2b3c)."""
    parts = [p for p in (profile_slug or "").split("-") if p and not any(ch.isdigit() for ch in p)]
    parts = parts or [profile_slug or ""]
    first = parts[0].title() or "LinkedIn"  # candidate creation requires a first name
    last = " ".join(parts[1:]).title() or "(LinkedIn)"
    return first, last

def _display_name(db: Session, item: LinkedInCandidatePipeline) -> str:
    if item.candidate_id:
        candidate = db.query(Candidate).filter(Candidate.candidateID == item.candidate_id).first()
        if candidate is not None:
            name = " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName]))
            if name:
                return name
    return " ".join(name_from_slug(item.linkedin_profile_slug)).replace(" (LinkedIn)", "")

def creation_idempotency_key(item: LinkedInCandidatePipeline, tenant_id: Optional[int]) -> str:
    # Same key format as candidate_creation_wrapper.queue_candidate_creation()
    if tenant_id is None:
        raise ValueError("creation_idempotency_key needs the tenant")
    return f"candidate_create:{placeholder_email(item.linkedin_profile_slug)}:{tenant_id}:{CANDIDATE_SOURCE}"

def queue_pipeline_candidate(
    db: Session,
    item: LinkedInCandidatePipeline,
    *,
    created_by_user_id: str,
    tenant_id: Optional[int],
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[str]:
    """Queue creation of the item's candidate (queue-first, no waiting). The
    creation handler links it to the item and its open task via
    linkedin_pipeline_id, with Thunder off until Import."""
    from app.services.candidate_creation_wrapper import queue_candidate_creation

    guess_first, guess_last = name_from_slug(item.linkedin_profile_slug)
    result = queue_candidate_creation(
        db=db,
        email=email or placeholder_email(item.linkedin_profile_slug),
        first_name=(first_name or "").strip() or guess_first,
        last_name=(last_name or "").strip() or guess_last,
        tenant_id=tenant_id if tenant_id is not None else sole_tenant_id(db),
        source=CANDIDATE_SOURCE,
        linkedin_url=item.linkedin_url,
        created_by_user_id=created_by_user_id,
        linkedin_pipeline_id=str(item.id),
        thunder_enabled=False,
    )
    return result.get("message_id")

def creation_pending(db: Session, item: LinkedInCandidatePipeline, tenant_id: Optional[int]) -> bool:
    from app.models.channel_queue import ChannelQueueItem
    return db.query(ChannelQueueItem).filter(
        ChannelQueueItem.idempotency_key == creation_idempotency_key(item, tenant_id),
        ChannelQueueItem.status != "FAILED",
    ).first() is not None

def sync_outreach_task(db: Session, item: LinkedInCandidatePipeline, tenant_id: Optional[int]) -> None:
    """Close the task for the previous stage and open one for the current
    stage, assigned to the pipeline item's owner and due today (so it lands
    on My Tasks), linked to the candidate when it exists. Caller commits."""
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
    name = _display_name(db, item)
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
    if item.candidate_id:
        task.candidate_id = item.candidate_id
        db.add(task)
    item.task_id = str(task.id)
    db.add(item)

def link_candidate_to_pipeline(db: Session, pipeline_id: str, candidate_id: str) -> None:
    """Called when a pipeline item's candidate exists (by the creation
    handler, or when found by LinkedIn profile): links the item and its open
    follow-up task, and retitles that task with the candidate's real name.
    Caller commits."""
    item = db.query(LinkedInCandidatePipeline).filter(LinkedInCandidatePipeline.id == pipeline_id).first()
    if item is None:
        logger.warning(f"[LinkedInPipeline] Pipeline item {pipeline_id} not found for candidate {candidate_id}")
        return
    if item.candidate_id and item.candidate_id != candidate_id:
        logger.warning(
            f"[LinkedInPipeline] Item {pipeline_id} already linked to {item.candidate_id}; "
            f"not relinking to {candidate_id}"
        )
        return
    item.candidate_id = candidate_id
    db.add(item)
    if item.task_id:
        task = db.query(Task).filter(Task.id == int(item.task_id)).first()
        if task is not None and task.status not in ("COMPLETED", "CANCELLED"):
            task.candidate_id = candidate_id
            stage = _STAGE_TASKS.get(item.status)
            if stage is not None:
                db.flush()
                task.title, task.description = (
                    part.format(name=_display_name(db, item), url=item.linkedin_url) for part in stage
                )
            db.add(task)
    logger.info(f"[LinkedInPipeline] Linked candidate {candidate_id} to pipeline item {pipeline_id}")

def backfill_outreach_tasks(db: Session) -> int:
    """For in-progress items from before tasks/candidates were created at
    queue time: open the missing follow-up task and queue the missing
    candidate. Idempotent (skips items that have a task, a candidate, or a
    pending creation) and skips items whose owner no longer exists."""
    from sqlalchemy import text
    from app.models.user import Users

    # Every uvicorn worker runs startup; only one may backfill, or each
    # creates its own copy of the missing tasks. Session-level lock because
    # items are committed one by one.
    if not db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _BACKFILL_LOCK_KEY}).scalar():
        logger.info("[LinkedInPipeline] Backfill already running in another process; skipping")
        return 0
    try:
        items = db.query(LinkedInCandidatePipeline).filter(
            LinkedInCandidatePipeline.status != LinkedInPipelineStatus.IMPORTED_TO_THUNDER,
            LinkedInCandidatePipeline.assigned_to_user_id.isnot(None),
        ).all()

        tasks_created = 0
        candidates_queued = 0
        for item in items:
            if item.task_id and item.candidate_id:
                continue
            item_id = item.id
            try:
                owner = db.query(Users).filter(Users.UserID == item.assigned_to_user_id).first()
                if owner is None:
                    logger.warning(
                        f"[LinkedInPipeline] Skipping backfill for {item_id}: "
                        f"owner {item.assigned_to_user_id!r} no longer exists"
                    )
                    continue
                if not item.task_id:
                    sync_outreach_task(db, item, owner.tenant_id)
                    tasks_created += 1
                db.commit()  # the worker must be able to see the item it links to
                if not item.candidate_id and not creation_pending(db, item, owner.tenant_id):
                    queue_pipeline_candidate(db, item, created_by_user_id=owner.UserID, tenant_id=owner.tenant_id)
                    candidates_queued += 1
            except Exception as exc:
                # One bad legacy row must not stop the rest
                db.rollback()
                logger.error(f"[LinkedInPipeline] Backfill failed for item {item_id}: {exc}", exc_info=True)
        if tasks_created or candidates_queued:
            logger.info(
                f"[LinkedInPipeline] Backfill: {tasks_created} task(s) opened, "
                f"{candidates_queued} candidate(s) queued"
            )
        return tasks_created + candidates_queued
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _BACKFILL_LOCK_KEY})
        db.commit()
