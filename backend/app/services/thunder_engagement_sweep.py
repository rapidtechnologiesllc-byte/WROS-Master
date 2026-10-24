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
    from app.models.thunder_email import ThunderCadenceState
    from app.services.candidate_contact_policy import is_contactable
    from app.services.thunder_mail.cadence_service import enqueue_once
    from app.services.thunder_pause_service import is_thunder_paused

    if not settings.THUNDER_ENGAGEMENT_ENABLED:
        return {"status": "disabled"}
    if is_thunder_paused(db):
        return {"status": "paused"}
    now = now or datetime.utcnow()
    since = now - timedelta(days=settings.THUNDER_ENGAGEMENT_LOOKBACK_DAYS)
    engaged = db.query(ThunderCadenceState.candidate_id)
    candidates = (db.query(Candidate)
                  .filter(Candidate.candidateCreatedAt >= since, Candidate.thunder_enabled.is_(True),
                          Candidate.tenant_id.isnot(None), ~Candidate.candidateID.in_(engaged))
                  .order_by(Candidate.candidateCreatedAt)
                  .limit(settings.THUNDER_ENGAGEMENT_BATCH).all())
    queued = skipped = 0
    for candidate in candidates:
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
    logger.info(f"[ThunderSweep] queued {queued}, skipped {skipped} (of {len(candidates)} not yet engaged)")
    return {"status": "ok", "queued": queued, "skipped": skipped, "considered": len(candidates)}
