from datetime import datetime
import logging
from typing import List, Optional

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.newsletter import Newsletter, NewsletterSubscriber
from app.schemas.newsletter import (
    NewsletterCreate,
    NewsletterUpdate,
    SubscriberCreate,
    NewsletterSendResult,
)
from app.core.logging import logger
from app.core.scheduler import add_job, remove_job
from app.utils.uniq_id_generator import newsletter_id_generator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    """Return current UTC time as a naive datetime (compatible with SQL Server DATETIME)."""
    return datetime.utcnow()


def _send_via_graph(access_token: str, to_email: str, subject: str, body_html: str) -> None:
    """
    Send one real email via Microsoft Graph's /me/sendMail, on behalf of
    whichever staff member's delegated OAuth session supplied
    access_token -- same pattern as
    app.api.v1.endpoints.msgraph.send_mail, duplicated at the HTTP-call
    level (not imported) to keep this service module independent of the
    endpoints layer. Raises requests.HTTPError on failure; callers count
    that as a per-recipient failure rather than letting one bad address
    kill the whole send.
    """
    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            }
        },
        timeout=15,
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# NewsletterService
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class NewsletterService:

    # ------------------------------------------------------------------
    # Subscriber operations
    # ------------------------------------------------------------------

    @staticmethod
    def get_subscriber(db: Session, email: str) -> Optional[NewsletterSubscriber]:
        return (
            db.query(NewsletterSubscriber)
            .filter(NewsletterSubscriber.email == email)
            .first()
        )

    @staticmethod
    def create_subscriber(db: Session, subscriber_in: SubscriberCreate) -> NewsletterSubscriber:
        existing = NewsletterService.get_subscriber(db, email=subscriber_in.email)
        if existing:
            if not existing.is_active:
                # Reactivate
                existing.is_active = True
                if subscriber_in.name:
                    existing.name = subscriber_in.name
                db.commit()
                db.refresh(existing)
                logger.info(f"Reactivated subscriber: {subscriber_in.email}")
            else:
                logger.info(f"Subscriber already active: {subscriber_in.email}")
            return existing

        new_sub = NewsletterSubscriber(
            email=subscriber_in.email,
            name=subscriber_in.name,
            is_active=subscriber_in.is_active,
        )
        db.add(new_sub)
        db.commit()
        db.refresh(new_sub)
        logger.info(f"New subscriber created: {subscriber_in.email}")
        return new_sub

    @staticmethod
    def unsubscribe(db: Session, email: str) -> NewsletterSubscriber:
        subscriber = NewsletterService.get_subscriber(db, email)
        if not subscriber:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscriber with email '{email}' not found",
            )
        subscriber.is_active = False
        db.commit()
        db.refresh(subscriber)
        logger.info(f"Unsubscribed: {email}")
        return subscriber

    @staticmethod
    def get_all_subscribers(
        db: Session, skip: int = 0, limit: int = 100
    ) -> List[NewsletterSubscriber]:
        return (
            db.query(NewsletterSubscriber)
            .order_by(NewsletterSubscriber.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Newsletter CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def create_newsletter(
        db: Session, newsletter_in: NewsletterCreate, user_id: str
    ) -> Newsletter:
        new_newsletter = Newsletter(
            id=newsletter_id_generator(),
            subject=newsletter_in.subject,
            content=newsletter_in.content,
            status="draft",
            created_by=user_id,
        )
        db.add(new_newsletter)
        db.commit()
        db.refresh(new_newsletter)
        logger.info(f"Newsletter created: {new_newsletter.id}")
        return new_newsletter

    @staticmethod
    def get_newsletter(db: Session, newsletter_id: str) -> Optional[Newsletter]:
        return db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

    @staticmethod
    def get_newsletter_or_404(db: Session, newsletter_id: str) -> Newsletter:
        newsletter = NewsletterService.get_newsletter(db, newsletter_id)
        if not newsletter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Newsletter '{newsletter_id}' not found",
            )
        return newsletter

    @staticmethod
    def get_all_newsletters(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
    ) -> List[Newsletter]:
        query = db.query(Newsletter)
        if status_filter:
            query = query.filter(Newsletter.status == status_filter)
        return (
            query.order_by(Newsletter.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_dispatched_newsletters(
        db: Session, skip: int = 0, limit: int = 100
    ) -> List[Newsletter]:
        """Return newsletters that have been scheduled or already sent, newest first."""
        return (
            db.query(Newsletter)
            .filter(Newsletter.status.in_(["scheduled", "sent"]))
            .order_by(Newsletter.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_newsletter(
        db: Session, newsletter_id: str, newsletter_in: NewsletterUpdate
    ) -> Newsletter:
        newsletter = NewsletterService.get_newsletter_or_404(db, newsletter_id)

        # Pydantic v2 — use model_dump (replaces deprecated .dict())
        update_data = newsletter_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(newsletter, key, value)

        db.commit()
        db.refresh(newsletter)
        logger.info(f"Newsletter updated: {newsletter_id}")
        return newsletter

    @staticmethod
    def delete_newsletter(db: Session, newsletter_id: str) -> None:
        newsletter = NewsletterService.get_newsletter_or_404(db, newsletter_id)

        # Clean up any scheduled APScheduler job
        job_id = f"send_newsletter_{newsletter.id}"
        try:
            remove_job(job_id)
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"Could not remove scheduler job '{job_id}': {exc}")

        db.delete(newsletter)
        db.commit()
        logger.info(f"Newsletter deleted: {newsletter_id}")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    @staticmethod
    def schedule_newsletter(
        db: Session, newsletter_id: str, scheduled_for: datetime
    ) -> Newsletter:
        newsletter = NewsletterService.get_newsletter_or_404(db, newsletter_id)

        # Validate: only draft or already-scheduled newsletters can be rescheduled
        if newsletter.status == "sent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reschedule a newsletter that has already been sent",
            )

        job_id = f"send_newsletter_{newsletter.id}"

        # Remove any pre-existing scheduled job first
        try:
            remove_job(job_id)
        except Exception:
            pass

        # Schedule the new APScheduler job BEFORE committing to DB,
        # so a scheduler failure doesn't leave DB in an inconsistent state.
        try:
            add_job(
                NewsletterService._send_newsletter_job,
                trigger="date",
                run_date=scheduled_for,
                args=[newsletter.id],
                id=job_id,
                replace_existing=True,
            )
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"Failed to schedule APScheduler job for {newsletter_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to schedule newsletter — please try again",
            )

        # Persist only after job is confirmed
        newsletter.scheduled_for = scheduled_for
        newsletter.status = "scheduled"
        db.commit()
        db.refresh(newsletter)
        logger.info(f"Newsletter {newsletter.id} scheduled for {scheduled_for}")
        return newsletter

    # ------------------------------------------------------------------
    # Immediate send
    # ------------------------------------------------------------------

    @staticmethod
    def send_newsletter_now(
        db: Session, newsletter_id: str, graph_access_token: str
    ) -> NewsletterSendResult:
        """
        Send a newsletter immediately to all active subscribers via real
        Microsoft Graph mail (see _send_via_graph). graph_access_token
        comes from the calling HR/Admin user's own delegated MS Graph
        session (app.api.v1.endpoints.newsletter's send_newsletter_now
        resolves it from their sign-in cookie before calling this) --
        there is no mock fallback; a caller with no Graph session gets a
        401 at the endpoint layer before ever reaching this function.
        """
        newsletter = NewsletterService.get_newsletter_or_404(db, newsletter_id)

        if newsletter.status == "sent":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Newsletter has already been sent",
            )

        subscribers: List[NewsletterSubscriber] = (
            db.query(NewsletterSubscriber)
            .filter(NewsletterSubscriber.is_active == True)  # noqa: E712
            .all()
        )

        logger.info(
            f"Sending newsletter {newsletter_id} immediately to {len(subscribers)} subscriber(s)"
        )

        failed = 0
        for sub in subscribers:
            try:
                _send_via_graph(
                    graph_access_token, sub.email, newsletter.subject, newsletter.content,
                )
            except Exception as exc:
               logger.error(f"Error: {str(exc)}", exc_info=True)
                logger.error(f"Failed to send to {sub.email}: {exc}")
                failed += 1

        # Cancel any pending scheduled job for this newsletter
        job_id = f"send_newsletter_{newsletter.id}"
        try:
            remove_job(job_id)
        except Exception:
            pass

        newsletter.status = "sent"
        newsletter.sent_at = _now_utc()
        db.commit()
        db.refresh(newsletter)

        sent_count = len(subscribers) - failed
        logger.info(f"Newsletter {newsletter_id} sent: {sent_count} ok, {failed} failed")
        return NewsletterSendResult(
            newsletter_id=newsletter_id,
            recipients_count=sent_count,
            message=f"Newsletter sent to {sent_count} subscriber(s) ({failed} failed)",
        )

    # ------------------------------------------------------------------
    # Background job (called by APScheduler)
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_newsletter_job(newsletter_id: str) -> None:
        """
        Async background job executed by APScheduler for scheduled sends.

        KNOWN LIMITATION, not silently mocked: real sending (see
        send_newsletter_now/_send_via_graph) needs a live MS Graph
        delegated-permission access token, which only exists tied to a
        signed-in user's in-memory session cookie (app.api.v1.endpoints.
        msgraph.user_tokens) at request time. This job fires later, on a
        timer, with no HTTP request or cookie in scope -- there is no
        token available here to send with, whether the newsletter was
        scheduled 5 minutes or 5 days ago. Sending real email from a
        scheduled job would need either an app-only Graph permission
        (Mail.Send, application-level, admin-consented in Azure AD -- not
        confirmed to exist for this app registration) or persisting a
        refreshable token at schedule time, neither of which this round
        implements. Marks the newsletter 'failed' with a clear reason
        instead of falsely marking 'sent' -- same principle as the
        LinkedIn mock fix: no fake success, ever.
        """
        from app.core.database import SessionLocal  # late import to avoid circular deps

        db: Session = SessionLocal()
        try:
            newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
            if not newsletter:
                logger.warning(f"[scheduler] Newsletter {newsletter_id} not found — skipping")
                return
            if newsletter.status != "scheduled":
                logger.warning(
                    f"[scheduler] Newsletter {newsletter_id} has status '{newsletter.status}' — skipping"
                )
                return

            logger.error(
                f"[scheduler] Newsletter {newsletter_id} cannot be sent: scheduled sends "
                "have no live MS Graph session to send through yet (see docstring). "
                "Marking 'failed' rather than falsely marking 'sent' -- use 'Send Now' "
                "instead, signed in via MS Graph, until scheduled sending is built for real."
            )
            newsletter.status = "failed"
            db.commit()
            return

        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[scheduler] Unhandled error for newsletter {newsletter_id}: {exc}")
            db.rollback()
            # Mark as failed so admins can see it
            try:
                newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
                if newsletter:
                    newsletter.status = "failed"
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()
