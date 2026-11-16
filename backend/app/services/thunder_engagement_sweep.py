"""Thunder first engagement (go-live 2026-10-13): make sure every contactable candidate is
engaged, not only the ones whose creation path happened to queue it.

Runs as the thunder_engagement_sweep scheduled job. Each run queues
engage_candidate_with_thunder (ThunderEngagementHandler: email cadence first, WhatsApp when
configured) for candidates who are contactable (candidate_contact_policy.is_contactable: real
email, Thunder on, outside a post-rejection no-contact period), were created in the look-back
window, and have no cadence yet. Idempotent: the queue task id is deterministic per candidate and
attempt. A candidate whose engagement message ended FAILED (before 2026-10-24 a failed learning
lookup aborted it before the cadence was saved) is queued again with the next attempt number,
never while an engagement for them is still in flight.
Kill switches: THUNDER_ENGAGEMENT_ENABLED and the global queue pause.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.models.candidate import Candidate

logger = logging.getLogger(__name__)

ENGAGE_TASK = "engage_candidate_with_thunder"
MAX_ENGAGE_ATTEMPTS = 3  # each attempt already retries inside the queue; past this a person looks


def engage_task_id(candidate_id: str, attempt: int = 1) -> str:
    return f"thunder-engage-{candidate_id}" + (f"-{attempt}" if attempt > 1 else "")


def _next_attempt(db: Session, candidate_id: str):
    """The attempt number to queue, or None while an engagement for the candidate is in flight or
    MAX_ENGAGE_ATTEMPTS have failed (each is FAILED on the Message Queue screen with its error)."""
    from app.models.channel_queue import ChannelQueueItem
    from app.services.message_queue_service import IN_FLIGHT_STATUSES

    earlier = db.query(ChannelQueueItem.id, ChannelQueueItem.status).filter(
        ChannelQueueItem.type == ENGAGE_TASK,
        ChannelQueueItem.payload["candidate_id"].as_string() == candidate_id).all()
    if any(status in IN_FLIGHT_STATUSES + ("RETRY",) for _, status in earlier):
        return None
    if len(earlier) >= MAX_ENGAGE_ATTEMPTS:
        logger.error(f"[ThunderSweep] {candidate_id}: {len(earlier)} engagement attempts failed; not queued again")
        return None
    return len(earlier) + 1


def backlog_guard(db: Session, now: datetime) -> None:
    """Nothing to expire: the sweep only ever looks THUNDER_ENGAGEMENT_LOOKBACK_DAYS back, so
    enabling it can't reach an old backlog."""
    from app.core.config import settings
    logger.info(f"[ThunderSweep] first run: candidates created before "
                f"{now - timedelta(days=settings.THUNDER_ENGAGEMENT_LOOKBACK_DAYS):%Y-%m-%d} are never engaged")


def run_sweep(db: Session, now: datetime = None) -> Dict:
    from app.core.config import settings
    from app.services.candidate_contact_policy import is_contactable
    from app.services.thunder_mail.cadence_service import enqueue_once
    from app.services.thunder_pause_service import is_thunder_paused

    if not settings.THUNDER_ENGAGEMENT_ENABLED:
        return {"status": "disabled"}
    if is_thunder_paused(db):
        return {"status": "paused"}
    now = now or datetime.utcnow()
    since = now - timedelta(days=settings.THUNDER_ENGAGEMENT_LOOKBACK_DAYS)
    queued = skipped = considered = 0
    after = None
    # Walks every not-yet-engaged candidate, oldest first, until THUNDER_ENGAGEMENT_BATCH are queued.
    # Until 2026-11-10 it looked at the oldest BATCH only: once that many could not be engaged (archived,
    # in a no-contact period, three failed attempts) every run re-read the same ones and nobody newer
    # was ever reached.
    while queued < settings.THUNDER_ENGAGEMENT_BATCH:
        page = _not_engaged(db, since, after).limit(settings.THUNDER_ENGAGEMENT_BATCH).all()
        if not page:
            break
        after = (page[-1].candidateCreatedAt, page[-1].candidateID)
        for candidate in page:
            if queued >= settings.THUNDER_ENGAGEMENT_BATCH:
                break
            considered += 1
            ok, reason = is_contactable(db, candidate)
            if not ok:
                skipped += 1
                continue
            attempt = _next_attempt(db, candidate.candidateID)
            if attempt is None:
                continue
            if enqueue_once(ENGAGE_TASK, engage_task_id(candidate.candidateID, attempt),
                            {"candidate_id": candidate.candidateID, "trigger": "engagement_sweep",
                             "tenant_id": candidate.tenant_id}, candidate.tenant_id):
                queued += 1
    logger.info(f"[ThunderSweep] queued {queued}, skipped {skipped} (of {considered} not yet engaged)")
    return {"status": "ok", "queued": queued, "skipped": skipped, "considered": considered}


def _not_engaged(db: Session, since: datetime, after):
    """Candidates created since `since` with Thunder on, a real email and no cadence yet, oldest
    first; `after` = (created at, id) of the last one already looked at."""
    from sqlalchemy import tuple_

    from app.models.thunder_email import ThunderCadenceState
    from app.services.linkedin_pipeline_task_service import PLACEHOLDER_EMAIL_DOMAIN

    query = db.query(Candidate).filter(
        Candidate.candidateCreatedAt >= since, Candidate.thunder_enabled.is_(True),
        Candidate.tenant_id.isnot(None), Candidate.candidateEmail.isnot(None), Candidate.candidateEmail != "",
        ~Candidate.candidateEmail.like(f"%@{PLACEHOLDER_EMAIL_DOMAIN}"),
        ~Candidate.candidateID.in_(db.query(ThunderCadenceState.candidate_id)))
    if after is not None:
        query = query.filter(tuple_(Candidate.candidateCreatedAt, Candidate.candidateID) > after)
    return query.order_by(Candidate.candidateCreatedAt, Candidate.candidateID)


def engage_now(db: Session, candidate: Candidate) -> bool:
    """Queue the first engagement for one candidate now (a real email was just added), with the
    same rules as the sweep: Thunder on, contactable, not yet in a cadence, no engagement in flight.
    Returns whether it was queued."""
    from app.core.config import settings
    from app.models.thunder_email import ThunderCadenceState
    from app.services.candidate_contact_policy import is_contactable
    from app.services.thunder_mail.cadence_service import enqueue_once
    from app.services.thunder_pause_service import is_thunder_paused

    if not settings.THUNDER_ENGAGEMENT_ENABLED or is_thunder_paused(db) or candidate.tenant_id is None:
        return False
    if db.query(ThunderCadenceState.candidate_id).filter_by(candidate_id=candidate.candidateID).first():
        return False
    if not is_contactable(db, candidate)[0]:
        return False
    attempt = _next_attempt(db, candidate.candidateID)
    if attempt is None:
        return False
    return enqueue_once(ENGAGE_TASK, engage_task_id(candidate.candidateID, attempt),
                        {"candidate_id": candidate.candidateID, "trigger": "email_added",
                         "tenant_id": candidate.tenant_id}, candidate.tenant_id)
