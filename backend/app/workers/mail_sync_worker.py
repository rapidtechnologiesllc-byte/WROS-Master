"""
Outlook mail-capture run (one pass, then exit).

Cron runs this every 15 minutes under flock (see scripts/deploy_backend.sh):
    python -m app.workers.mail_sync_worker

It syncs every user who connected Outlook: new Inbox / Sent Items messages
whose other party is a known candidate or employee are linked to that
person's history (metadata only). Then it reads the Thunder mailbox for
candidate replies and queues every due Thunder email (silence follow-ups,
monthly nurture). Runs on its own rather than through the in-process
APScheduler, which is not started in production.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [MAIL-SYNC] - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    import app.core.config  # noqa: F401 -- loads .env before anything reads settings
    from app.core.database import SessionLocal
    from app.services.msgraph_mail_sync_service import run_msgraph_mail_sync_job

    from app.services.thunder_mail.mail_poll_service import poll_thunder_mailbox, run_cadence_sweep

    failed = False
    # Independent sessions: one job failing never blocks the others
    for name, job in (("Mail sync", run_msgraph_mail_sync_job),
                      ("Thunder mailbox poll", poll_thunder_mailbox),
                      ("Thunder cadence sweep", run_cadence_sweep)):
        db = SessionLocal()
        try:
            logger.info(f"{name} complete: {job(db)}")
        except Exception as exc:
            failed = True
            db.rollback()
            logger.error(f"{name} failed: {exc}", exc_info=True)
        finally:
            db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
