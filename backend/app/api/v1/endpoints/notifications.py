"""
S-105/HRMS-P210 -- Portal Notification Center -- API Endpoints
=========================================================================
Prefix: /notifications
import logging
Tag:    notifications

Wires app.services.notification_service (HRMS-0113, real, tested,
already-shipped dispatch engine -- multiple stories this session
already call send_notification()) to real HTTP routes for the first
time. HRMS-0113's own model docstring flagged this exact gap: "the
in-app notification bell / nav shell UI ... get_unread_count()/
mark_as_read() are the backend a future UI would call." This is that
UI's read/write surface.

Always scoped to the CALLING user (current_user.UserID) -- never a
path param -- there's no reason anyone should read another user's
notification feed, and a path param would invite exactly that.

Routes:
  GET   /notifications               This user's IN_APP feed + unread count.
  POST  /notifications/{id}/mark-read   Mark one notification read.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.notification import Notification
from app.models.user import Users
from app.schemas.notification import NotificationItem, NotificationListResponse
from app.services.notification_service import (
    get_notifications_for_user,
    get_unread_count,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_item(n: Notification) -> NotificationItem:
    return NotificationItem(
        id=n.id, channel=n.channel, priority_tier=n.priority_tier, message=n.message,
        delivery_status=n.delivery_status, sent_at=n.sent_at, read_at=n.read_at, created_at=n.created_at,
    )


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="This user's in-app notification feed + unread count",
    dependencies=[Depends(require_resource_permission("notifications", "view"))]
)
def list_notifications(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    notifications = get_notifications_for_user(db, current_user.UserID, tenant_id=current_user.tenant_id)
    unread = get_unread_count(db, current_user.UserID, tenant_id=current_user.tenant_id)
    return NotificationListResponse(notifications=[_to_item(n) for n in notifications], unread_count=unread)


@router.post(
    "/{notification_id}/mark-read",
    response_model=NotificationItem,
    summary="Mark one notification read",
    dependencies=[Depends(require_resource_permission("notifications", "create"))]
)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id, Notification.recipient_id == current_user.UserID,
    ).first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification = mark_as_read(db, notification)
    db.commit()
    db.refresh(notification)
    return _to_item(notification)
