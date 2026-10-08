"""Run due background jobs once, then exit. Cron runs this every 5 minutes
under flock (scripts/deploy_backend.sh):

    python -m app.workers.scheduled_jobs_worker

Replaces the in-process APScheduler (app/core/scheduler.py), which production
never starts. Only jobs named in SCHEDULED_JOBS_ENABLED run. A row lock on
scheduled_job_runs makes each job run at most once per interval even if two
hosts or two overlapping cron runs start together.
"""
import importlib
import logging
import sys
import uuid
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.dialects.postgresql import insert

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [SCHEDULED-JOBS] - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_ERROR_CHARS = 4000


class JobConfigError(RuntimeError):
    """SCHEDULED_JOBS_ENABLED names an unknown job, or an external job without a backlog guard."""


def _resolve(target: str) -> Callable:
    module, attr = target.split(":")
    return getattr(importlib.import_module(module), attr)


def enabled_jobs(enabled: str, registry: Dict) -> List:
    names = [n.strip() for n in (enabled or "").split(",") if n.strip()]
    unknown = [n for n in names if n not in registry]
    if unknown:
        raise JobConfigError(f"SCHEDULED_JOBS_ENABLED has unknown jobs: {unknown}")
    unguarded = [n for n in names if registry[n].sends_external and not registry[n].backlog_guard]
    if unguarded:
        raise JobConfigError(f"Jobs contacting people need a backlog_guard before they can run: {unguarded}")
    return [registry[n] for n in names]


def _is_due(job, row, now: datetime) -> bool:
    if row.running_until is not None and row.running_until > now:
        return False  # another run holds the lease
    if row.last_started_at is None:
        due_by_interval = True
    else:
        due_by_interval = now - row.last_started_at >= job.interval
    if job.daily_after_utc:
        hour, minute = (int(x) for x in job.daily_after_utc.split(":"))
        not_today = row.last_started_at is None or row.last_started_at.date() < now.date()
        return not_today and now.time() >= time(hour, minute)
    return due_by_interval


def claim(db, job, now: datetime, grace_s: int) -> Tuple[Optional[str], bool]:
    """Commit a lease on the job if it is due. Returns (lease token or None, is first run ever)."""
    from app.models.scheduled_job_run import ScheduledJobRun

    db.execute(insert(ScheduledJobRun).values(name=job.name, run_count=0, consecutive_failures=0)
               .on_conflict_do_nothing(index_elements=["name"]))
    row = db.query(ScheduledJobRun).filter_by(name=job.name).with_for_update().one()
    if not _is_due(job, row, now):
        db.commit()
        return None, False
    token = str(uuid.uuid4())
    first_run = row.first_enabled_at is None
    row.lease_token, row.running_until = token, now + timedelta(seconds=job.timeout_s + grace_s)
    row.last_started_at, row.last_status = now, "RUNNING"
    if first_run:
        row.first_enabled_at = now
    db.commit()
    return token, first_run


def finish(db, job, token: str, status: str, result=None, error: Optional[str] = None,
           now: Optional[datetime] = None) -> bool:
    """Record the outcome; a run whose lease was taken over (stale token) changes nothing."""
    from app.models.scheduled_job_run import ScheduledJobRun

    row = db.query(ScheduledJobRun).filter_by(name=job.name, lease_token=token).with_for_update().first()
    if row is None:
        db.rollback()
        logger.warning(f"{job.name}: lease lost before finish; outcome {status} not recorded")
        return False
    row.lease_token, row.running_until = None, None
    row.last_finished_at, row.last_status = now or datetime.utcnow(), status
    row.last_result, row.last_error = result, (error or None) and error[:MAX_ERROR_CHARS]
    row.run_count = (row.run_count or 0) + 1
    row.consecutive_failures = 0 if status == "SUCCESS" else (row.consecutive_failures or 0) + 1
    db.commit()
    return True


def _jsonable(result):
    if isinstance(result, dict):
        return {k: v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)
                for k, v in result.items()}
    if isinstance(result, (list, tuple)):
        return {"count": len(result)}
    if isinstance(result, (int, float)):
        return {"count": result}
    return {"result": None if result is None else str(result)}


def run_once(session_factory=None, now: Optional[datetime] = None, enabled: Optional[str] = None,
             registry: Optional[Dict] = None, run_with_timeout: Optional[Callable] = None) -> Dict:
    from app.core.config import settings
    from app.core.scheduled_jobs import JOBS
    from app.workers.message_queue_worker import HandlerTimeoutError, with_timeout

    if session_factory is None:
        from app.core.database import SessionLocal
        session_factory = SessionLocal
    registry = registry if registry is not None else JOBS
    jobs = enabled_jobs(settings.SCHEDULED_JOBS_ENABLED if enabled is None else enabled, registry)
    run_with_timeout = run_with_timeout or (lambda fn, seconds, *args: with_timeout(seconds)(fn)(*args))
    outcomes: Dict[str, str] = {}

    for job in jobs:
        started = now or datetime.utcnow()
        db = session_factory()
        try:
            token, first_run = claim(db, job, started, settings.SCHEDULED_JOB_LEASE_GRACE_SECONDS)
        except Exception as exc:
            db.rollback()
            db.close()
            logger.error(f"{job.name}: could not claim: {exc}", exc_info=True)
            outcomes[job.name] = "CLAIM_FAILED"
            continue
        if token is None:
            db.close()
            outcomes[job.name] = "NOT_DUE"
            continue
        logger.info(f"{job.name}: start")

        status, result, error = "SUCCESS", None, None
        work = session_factory()
        try:
            if first_run and job.backlog_guard:
                _resolve(job.backlog_guard)(work, started)
                work.commit()
            result = _jsonable(run_with_timeout(_resolve(job.target), job.timeout_s, work))
            work.commit()
        except HandlerTimeoutError as exc:
            work.rollback()
            status, error = "TIMEOUT", str(exc)
        except Exception as exc:
            work.rollback()
            status, error = "FAILED", f"{type(exc).__name__}: {exc}"
            logger.error(f"{job.name}: failed: {exc}", exc_info=True)
        finally:
            work.close()

        try:
            finish(db, job, token, status, result, error)
        finally:
            db.close()
        outcomes[job.name] = status
        logger.info(f"{job.name}: {status} {result or error or ''}")
    return outcomes


def main() -> int:
    import app.core.config  # noqa: F401 -- loads .env before anything reads settings
    import app.models  # noqa: F401 -- all tables known to SQLAlchemy

    try:
        outcomes = run_once()
    except JobConfigError as exc:
        logger.error(str(exc))
        return 1
    logger.info(f"Run complete: {outcomes}")
    return 1 if any(s in ("FAILED", "TIMEOUT", "CLAIM_FAILED") for s in outcomes.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
