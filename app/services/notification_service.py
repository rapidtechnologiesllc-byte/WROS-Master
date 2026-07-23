"""
HRMS-0113 -- Notification Engine Base. sendNotification() is meant to
be the single entry point every other story calls instead of building
its own send logic (per CLAUDE.md's non-negotiables) -- see
app.models.notification's docstring for what's genuinely out of scope
(WhatsApp/SMS providers not provisioned, no nav-shell UI) versus what's
built for real here (the full dispatch/fallback/gating state machine).
"""
import datetime as dt
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.notification import NOTIFICATION_CHANNELS, PRIORITY_TIERS, Notification
from app.models.user import Users
from app.services.email_service import EmailService

DEFAULT_TIMEZONE = "Asia/Kolkata"
# BR-0113-03's stated default; HRMS-0121 (the story meant to make this
# per-tenant configurable) doesn't exist in this codebase.
BUSINESS_HOURS_START = 8   # 08:00 local
BUSINESS_HOURS_END = 20    # 20:00 local

# BR-0113-01: P0's fallback partner. SMS is the documented P0 fallback
# channel; if SMS was already the primary, WhatsApp is the fallback
# instead (S-211 says "SMS+WhatsApp fallback" without a stricter order).
P0_FALLBACK_CHANNEL = {
    "IN_APP": "SMS", "EMAIL": "SMS", "WHATSAPP": "SMS", "SMS": "WHATSAPP",
}


class CrossTenantNotificationError(Exception):
    """BR-0113-02."""


class ChannelNotConfigured(Exception):
    """WhatsApp/SMS integrations aren't provisioned in this codebase yet."""


class InvalidPriorityTier(Exception):
    pass


class InvalidChannel(Exception):
    pass


def _send_in_app(recipient: Users, message: str) -> bool:
    return True  # the notifications row itself IS the in-app delivery


def _send_email(recipient: Users, message: str) -> bool:
    if not recipient.UserEmail:
        return False
    try:
        EmailService.send_notification(
            to_email=recipient.UserEmail, heading="BlitzenX Notification", message=message,
        )
        return True
    except Exception:
        return False


def _send_whatsapp_unconfigured(recipient: Users, message: str) -> bool:
    raise ChannelNotConfigured("WhatsApp Business API is not provisioned in this codebase yet.")


def _send_sms_unconfigured(recipient: Users, message: str) -> bool:
    raise ChannelNotConfigured("SMS gateway is not provisioned in this codebase yet.")


DEFAULT_CHANNEL_SENDERS: Dict[str, Callable[[Users, str], bool]] = {
    "IN_APP": _send_in_app,
    "EMAIL": _send_email,
    "WHATSAPP": _send_whatsapp_unconfigured,
    "SMS": _send_sms_unconfigured,
}


def _is_within_business_hours(
    now_utc: dt.datetime, tz_name: str,
    *, start_hour: int = BUSINESS_HOURS_START, end_hour: int = BUSINESS_HOURS_END,
) -> bool:
    """Generalized so callers with a different window (e.g.
    app.services.conversation_inactivity_service's 9am-9pm candidate
    send-window) can reuse this same tested timezone-conversion logic
    instead of duplicating it."""
    tz = ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    local_now = now_utc.replace(tzinfo=dt.timezone.utc).astimezone(tz)
    return start_hour <= local_now.hour < end_hour


def _next_business_hours_release(
    now_utc: dt.datetime, tz_name: str,
    *, start_hour: int = BUSINESS_HOURS_START, end_hour: int = BUSINESS_HOURS_END,
) -> dt.datetime:
    """Next moment (naive UTC, matching this codebase's DateTime
    convention elsewhere) the recipient's local time enters the
    [start_hour, end_hour) window."""
    tz = ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    local_now = now_utc.replace(tzinfo=dt.timezone.utc).astimezone(tz)
    candidate = local_now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    if local_now.hour >= end_hour:
        candidate += dt.timedelta(days=1)
    return candidate.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _dispatch_now(
    notification: Notification, recipient: Users, message: str, channel: str,
    senders: Dict[str, Callable[[Users, str], bool]], *, allow_p0_fallback: bool,
) -> None:
    sender = senders.get(channel, senders.get("EMAIL"))
    try:
        ok = bool(sender and sender(recipient, message))
    except ChannelNotConfigured:
        ok = False

    if ok:
        notification.delivery_status = "SENT"
        notification.sent_at = dt.datetime.utcnow()
        return

    if allow_p0_fallback:
        fallback_channel = P0_FALLBACK_CHANNEL.get(channel, "SMS")
        fallback_sender = senders.get(fallback_channel)
        try:
            fallback_ok = bool(fallback_sender and fallback_sender(recipient, message))
        except ChannelNotConfigured:
            fallback_ok = False

        if fallback_ok:
            notification.fallback_channel = fallback_channel
            notification.delivery_status = "FALLBACK_SENT"
            notification.sent_at = dt.datetime.utcnow()
            return

    # P0 with no successful channel is itself an incident per S-211's
    # own SMS-gateway integration note -- surfacing that alert (paging
    # whoever owns platform incidents) is out of scope here; the status
    # is recorded so a caller/monitor can act on it.
    notification.delivery_status = "FAILED"


def send_notification(
    db: Session,
    *,
    calling_context_tenant_id: Optional[int],
    recipient: Users,
    priority_tier: str,
    message: str,
    channel_preference: str = "EMAIL",
    channel_senders: Optional[Dict[str, Callable[[Users, str], bool]]] = None,
    now: Optional[dt.datetime] = None,
) -> Notification:
    """HRMS-0113 Step 2 -- the single entry point every other story
    should call instead of implementing its own send logic."""
    if priority_tier not in PRIORITY_TIERS:
        raise InvalidPriorityTier(f"priority_tier must be one of {PRIORITY_TIERS}, got '{priority_tier}'.")
    if channel_preference not in NOTIFICATION_CHANNELS:
        raise InvalidChannel(f"channel_preference must be one of {NOTIFICATION_CHANNELS}, got '{channel_preference}'.")

    # BR-0113-02
    if recipient.tenant_id != calling_context_tenant_id:
        raise CrossTenantNotificationError(
            f"Recipient {recipient.UserID} belongs to tenant {recipient.tenant_id}, "
            f"not the calling context's tenant {calling_context_tenant_id}."
        )

    senders = channel_senders or DEFAULT_CHANNEL_SENDERS
    now = now or dt.datetime.utcnow()

    notification = Notification(
        tenant_id=calling_context_tenant_id, recipient_id=recipient.UserID,
        channel=channel_preference, priority_tier=priority_tier, message=message,
        delivery_status="PENDING",
    )

    if priority_tier == "P0":
        # BR-0113-03: P0 is the sole exception -- bypasses business-hours gating entirely.
        _dispatch_now(notification, recipient, message, channel_preference, senders, allow_p0_fallback=True)
    elif _is_within_business_hours(now, recipient.timezone):
        _dispatch_now(notification, recipient, message, channel_preference, senders, allow_p0_fallback=False)
    else:
        notification.scheduled_release_at = _next_business_hours_release(now, recipient.timezone)
        # delivery_status stays PENDING -- release_pending_notifications() sends it later.

    db.add(notification)
    return notification


def release_pending_notifications(
    db: Session, *, now: Optional[dt.datetime] = None,
    channel_senders: Optional[Dict[str, Callable[[Users, str], bool]]] = None,
) -> int:
    """
    The function a cron would call to actually send P1/P2 notifications
    once their business-hours hold expires. Not wired to a scheduler in
    this build -- same "idempotent function exists, cron wiring is
    follow-up" posture as timesheet_service.create_weekly_draft().
    Returns the count of notifications processed (sent or failed).
    """
    now = now or dt.datetime.utcnow()
    senders = channel_senders or DEFAULT_CHANNEL_SENDERS

    pending = db.query(Notification).filter(
        Notification.delivery_status == "PENDING",
        Notification.scheduled_release_at.isnot(None),
        Notification.scheduled_release_at <= now,
    ).all()

    processed = 0
    for notification in pending:
        recipient = db.query(Users).filter(Users.UserID == notification.recipient_id).first()
        if recipient is None:
            notification.delivery_status = "FAILED"
            db.add(notification)
            processed += 1
            continue
        _dispatch_now(
            notification, recipient, notification.message, notification.channel,
            senders, allow_p0_fallback=False,
        )
        db.add(notification)
        processed += 1

    return processed


def mark_as_read(db: Session, notification: Notification) -> Notification:
    notification.read_at = dt.datetime.utcnow()
    db.add(notification)
    return notification


def get_notifications_for_user(
    db: Session, recipient_id: str, *, tenant_id: Optional[int] = None, limit: int = 50,
) -> List[Notification]:
    """S-105/HRMS-P210 Portal Notification Center: the in-app bell/feed
    HRMS-0113's own docstring said would be a future UI's job -- this is
    that future UI's read backend. IN_APP channel only (EMAIL/WHATSAPP/
    SMS rows are outbound dispatch records, not feed items), most recent
    first."""
    return (
        db.query(Notification)
        .filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == tenant_id,
            Notification.channel == "IN_APP",
            Notification.delivery_status.in_(("SENT", "FALLBACK_SENT")),
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session, recipient_id: str, tenant_id: Optional[int] = None) -> int:
    """Backend for HRMS-0113 Step 4's notification bell -- counts
    delivered (not merely held-pending) in-app notifications only."""
    return db.query(Notification).filter(
        Notification.recipient_id == recipient_id,
        Notification.tenant_id == tenant_id,
        Notification.channel == "IN_APP",
        Notification.delivery_status.in_(("SENT", "FALLBACK_SENT")),
        Notification.read_at.is_(None),
    ).count()
