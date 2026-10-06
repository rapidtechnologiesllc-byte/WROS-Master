"""
Outlook mail-capture run (one pass, then exit).

Cron runs this every 15 minutes under flock (see scripts/deploy_backend.sh):
    python -m app.workers.mail_sync_worker

It syncs every user who connected Outlook: new Inbox / Sent Items messages
whose other party is a known candidate or employee are linked to that
person's history (metadata only). Runs on its own rather than through the
in-process APScheduler, which also holds the Thunder outreach jobs and is
not started in production.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [MAIL-SYNC] - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    import app.core.config  # noqa: F401 -- loads .env before anything reads settings
    from app.core.database import SessionLocal
    from app.services.msgraph_mail_sync_service import run_msgraph_mail_sync_job

    db = SessionLocal()
    try:
        result = run_msgraph_mail_sync_job(db)
        logger.info(f"Mail sync complete: {result}")
        return 0
    except Exception as exc:
        logger.error(f"Mail sync run failed: {exc}", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
