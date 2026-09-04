from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import logging
from typing import List, Optional

from app.core.database import get_db
from app.schemas.newsletter import (
    NewsletterCreate,
    NewsletterUpdate,
    NewsletterResponse,
    NewsletterSchedule,
    NewsletterSendResult,
    SubscriberCreate,
    SubscriberResponse,
)
from app.services.newsletter_service import NewsletterService
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.api.v1.endpoints.msgraph import _require_account, _graph_client_for

router = APIRouter(prefix="/newsletters", tags=["Newsletter"])

# ===========================================================================
# Subscriber Endpoints
# ===========================================================================

@router.post(
    "/subscribe",
    response_model=SubscriberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe an email to the newsletter",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def subscribe_newsletter(
    subscriber_in: SubscriberCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Subscribe an email address to the newsletter.
    - If the email doesn't exist, a new subscriber is created.
    - If the email exists but is inactive, it is reactivated.
    - If the email is already active, the existing record is returned as-is.
    """
    try:
        return NewsletterService.create_subscriber(db, subscriber_in)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error subscribing '{subscriber_in.email}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process subscription",
        )

@router.delete(
    "/unsubscribe/{email}",
    response_model=SubscriberResponse,
    summary="Unsubscribe an email from the newsletter",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def unsubscribe_newsletter(
    email: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Deactivate an email address so it no longer receives newsletters.
    Returns 404 if the subscriber does not exist.
    """
    try:
        return NewsletterService.unsubscribe(db, email)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error unsubscribing '{email}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process unsubscription",
        )

@router.get(
    "/subscribers",
    response_model=List[SubscriberResponse],
    summary="List all newsletter subscribers",
    dependencies=[Depends(require_resource_permission("newsletters", "view"))],
)
def get_subscribers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Retrieve a paginated list of all newsletter subscribers."""
    return NewsletterService.get_all_subscribers(db, skip=skip, limit=limit)

# ===========================================================================
# Newsletter Endpoints
# ===========================================================================

@router.post(
    "/create",
    response_model=NewsletterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a newsletter draft",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def create_newsletter(
    newsletter_in: NewsletterCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Create a new newsletter in 'draft' status."""
    try:
        return NewsletterService.create_newsletter(db, newsletter_in, user_id=user.UserID)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error creating newsletter: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create newsletter",
        )

@router.get(
    "/all",
    response_model=List[NewsletterResponse],
    summary="List all newsletters (optionally filtered by status)",
    dependencies=[Depends(require_resource_permission("newsletters", "view"))],
)
def get_newsletters(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Retrieve a paginated list of all newsletters, newest first.
    
    Pass an optional `status` query param to filter:
    - `draft` â€” unpublished drafts
    - `scheduled` â€” queued for future delivery
    - `sent` â€” already delivered
    - `failed` â€” delivery failed
    """
    return NewsletterService.get_all_newsletters(db, skip=skip, limit=limit, status_filter=status)

@router.get(
    "/dispatched",
    response_model=List[NewsletterResponse],
    summary="List newsletters that have been scheduled or sent",
    dependencies=[Depends(require_resource_permission("newsletters", "view"))],
)
def get_dispatched_newsletters(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Return only newsletters with status `scheduled` or `sent` â€” i.e. every
    newsletter that an admin has dispatched (queued or already delivered).
    Results are ordered newest-first.
    """
    return NewsletterService.get_dispatched_newsletters(db, skip=skip, limit=limit)

@router.put(
    "/update/{newsletter_id}",
    response_model=NewsletterResponse,
    summary="Update a newsletter draft",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def update_newsletter(
    newsletter_id: str,
    newsletter_in: NewsletterUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """Partially update fields on an existing newsletter. Returns 404 if not found."""
    try:
        return NewsletterService.update_newsletter(db, newsletter_id, newsletter_in)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error updating newsletter '{newsletter_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update newsletter",
        )

@router.post(
    "/schedule/{newsletter_id}",
    response_model=NewsletterResponse,
    summary="Schedule a newsletter for future delivery",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def schedule_newsletter(
    newsletter_id: str,
    schedule_data: NewsletterSchedule,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Schedule an existing draft (or reschedule a previously scheduled) newsletter.
    Returns 400 if the newsletter has already been sent.
    """
    try:
        return NewsletterService.schedule_newsletter(
            db,
            newsletter_id=newsletter_id,
            scheduled_for=schedule_data.scheduled_for,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error scheduling newsletter '{newsletter_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule newsletter",
        )

@router.post(
    "/send/{newsletter_id}",
    response_model=NewsletterSendResult,
    summary="Send a newsletter immediately",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def send_newsletter_now(
    newsletter_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Immediately send a newsletter to all active subscribers via the
    caller's own signed-in Microsoft Graph session (same delegated-
    permission /me/sendMail pattern used for interview scheduling mail).
    Requires having signed in at GET /msgraph/auth/signin first.

    Deliberately re-raised as 403, not the 401 _require_account/
    _graph_client_for themselves raise: the frontend's apiRequest
    treats ANY 401 as "your JWT expired" and wipes the whole app
    session + redirects to login, which would silently log the caller
    out of the entire app instead of showing this specific, actionable
    message -- a real bug that would have shipped if this used 401.
    """
    try:
        account_id = _require_account(request)
        access_token = _graph_client_for(account_id)["access_token"]
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Sending a newsletter requires a signed-in Microsoft Graph "
                "session. Sign in at GET /msgraph/auth/signin, then try again."
            ),
        )
    try:
        return NewsletterService.send_newsletter_now(db, newsletter_id, access_token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error sending newsletter '{newsletter_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send newsletter",
        )

@router.delete(
    "/delete/{newsletter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a newsletter",
    dependencies=[Depends(require_resource_permission("newsletters", "edit"))],
)
def delete_newsletter(
    newsletter_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Permanently delete a newsletter and cancel any associated scheduled job.
    Returns 404 if the newsletter does not exist.
    """
    try:
        NewsletterService.delete_newsletter(db, newsletter_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"Error deleting newsletter '{newsletter_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete newsletter",
        )
