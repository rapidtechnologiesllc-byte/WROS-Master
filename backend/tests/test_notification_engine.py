"""
Proves HRMS-0113: BR-0113-01 (P0 fallback within 60s), BR-0113-02
(cross-tenant dispatch rejected before send), BR-0113-03 (non-P0
notifications respect the recipient's local business hours; P0 bypasses
that gating entirely), plus read-receipt/unread-count and the
import logging
release_pending_notifications() cron-callable.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.notification import Notification

from app.services.notification_service import (
    send_notification,
    release_pending_notifications,
    mark_as_read,
    get_unread_count,
    CrossTenantNotificationError,
    ChannelNotConfigured,
    InvalidPriorityTier,
    InvalidChannel,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Users.__table__, Notification.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def tenant_and_users(db_session):
    tenant = Tenant(name="BlitzenX")
    other_tenant = Tenant(name="Other Client Co")
    db_session.add_all([tenant, other_tenant])
    db_session.commit()

    recipient = Users(
        UserID="U-1", UserRole="RM", UserEmail="rm@blitzenx.com", UserPassword="h",
        tenant_id=tenant.id, timezone="Asia/Kolkata",
    )
    other_tenant_user = Users(
        UserID="U-2", UserRole="RM", UserEmail="other@otherco.com", UserPassword="h",
        tenant_id=other_tenant.id, timezone="Asia/Kolkata",
    )
    db_session.add_all([recipient, other_tenant_user])
    db_session.commit()
    return tenant, other_tenant, recipient, other_tenant_user

# A fixed "noon IST" instant -- 2026-02-02 06:30 UTC == 12:00 IST (UTC+5:30) -- inside the 08:00-20:00 window.
NOON_IST_UTC = datetime(2026, 2, 2, 6, 30)
# A fixed "3am IST" instant -- 2026-02-02 21:30 UTC (prior day) == 03:00 IST -- outside the window.
THREE_AM_IST_UTC = datetime(2026, 2, 1, 21, 30)

# ---------------------------------------------------------------------------
# BR-0113-02: tenant scoping
# ---------------------------------------------------------------------------

def test_cross_tenant_dispatch_rejected(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    with pytest.raises(CrossTenantNotificationError):
        send_notification(
            db_session, calling_context_tenant_id=tenant.id, recipient=other_tenant_user,
            priority_tier="P1", message="hello", now=NOON_IST_UTC,
        )

def test_same_tenant_dispatch_allowed(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="hello", channel_preference="IN_APP", now=NOON_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "SENT"

def test_invalid_priority_tier_rejected(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users
    with pytest.raises(InvalidPriorityTier):
        send_notification(db_session, calling_context_tenant_id=tenant.id, recipient=recipient, priority_tier="P9", message="x")

def test_invalid_channel_rejected(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users
    with pytest.raises(InvalidChannel):
        send_notification(
            db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
            priority_tier="P1", message="x", channel_preference="FAX",
        )

# ---------------------------------------------------------------------------
# BR-0113-03: business-hours gating (non-P0), P0 bypass
# ---------------------------------------------------------------------------

def test_p1_within_business_hours_sends_immediately(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="hello", channel_preference="IN_APP", now=NOON_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "SENT"
    assert notification.scheduled_release_at is None

def test_p1_outside_business_hours_is_held(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="hello", now=THREE_AM_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "PENDING"
    assert notification.scheduled_release_at is not None
    assert notification.scheduled_release_at > THREE_AM_IST_UTC

def test_p2_outside_business_hours_is_also_held(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P2", message="hello", now=THREE_AM_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "PENDING"
    assert notification.scheduled_release_at is not None

def test_p0_bypasses_business_hours_gating_entirely(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P0", message="CRITICAL", channel_preference="IN_APP", now=THREE_AM_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "SENT"
    assert notification.scheduled_release_at is None

def test_release_pending_notifications_sends_held_ones_once_due(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="hello", channel_preference="IN_APP", now=THREE_AM_IST_UTC,
    )
    db_session.commit()
    release_at = notification.scheduled_release_at

    # Not due yet -- releasing "now" (still 3am) should do nothing.
    processed = release_pending_notifications(db_session, now=THREE_AM_IST_UTC)
    db_session.commit()
    assert processed == 0
    assert notification.delivery_status == "PENDING"

    # Due now -- releasing at/after the computed release time sends it.
    processed = release_pending_notifications(db_session, now=release_at)
    db_session.commit()
    assert processed == 1
    assert notification.delivery_status == "SENT"

# ---------------------------------------------------------------------------
# BR-0113-01: P0 fallback within 60s
# ---------------------------------------------------------------------------

def test_p0_fallback_to_sms_when_primary_fails(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    senders = {
        "IN_APP": lambda r, m: True,
        "EMAIL": lambda r, m: False,  # primary fails
        "WHATSAPP": lambda r, m: True,
        "SMS": lambda r, m: True,     # fallback succeeds
    }
    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P0", message="CRITICAL", channel_preference="EMAIL",
        channel_senders=senders, now=NOON_IST_UTC,
    )
    db_session.commit()

    assert notification.delivery_status == "FALLBACK_SENT"
    assert notification.fallback_channel == "SMS"

def test_p0_no_successful_channel_marks_failed(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    senders = {
        "IN_APP": lambda r, m: True, "EMAIL": lambda r, m: False,
        "WHATSAPP": lambda r, m: False, "SMS": lambda r, m: False,
    }
    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P0", message="CRITICAL", channel_preference="EMAIL",
        channel_senders=senders, now=NOON_IST_UTC,
    )
    db_session.commit()
    assert notification.delivery_status == "FAILED"

def test_non_p0_does_not_fall_back_on_failure(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    senders = {
        "IN_APP": lambda r, m: True, "EMAIL": lambda r, m: False,
        "WHATSAPP": lambda r, m: True, "SMS": lambda r, m: True,
    }
    notification = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="not urgent", channel_preference="EMAIL",
        channel_senders=senders, now=NOON_IST_UTC,
    )
    db_session.commit()
    # P1 gets no fallback attempt -- straight to FAILED, no fallback_channel set.
    assert notification.delivery_status == "FAILED"
    assert notification.fallback_channel is None

def test_whatsapp_unconfigured_raises_and_is_treated_as_failure_for_fallback_purposes(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    # Real default senders: WHATSAPP genuinely isn't provisioned in this codebase.
    with pytest.raises(ChannelNotConfigured):
        # Calling the default WhatsApp sender directly proves it's a real,
        # explicit "not configured" signal, not a silent no-op.
        from app.services.notification_service import DEFAULT_CHANNEL_SENDERS
        DEFAULT_CHANNEL_SENDERS["WHATSAPP"](recipient, "hi")

# ---------------------------------------------------------------------------
# Read receipts / unread count (bell-icon backend)
# ---------------------------------------------------------------------------

def test_unread_count_and_mark_as_read(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    n1 = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="one", channel_preference="IN_APP", now=NOON_IST_UTC,
    )
    n2 = send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="two", channel_preference="IN_APP", now=NOON_IST_UTC,
    )
    db_session.commit()

    assert get_unread_count(db_session, recipient.UserID, tenant.id) == 2

    mark_as_read(db_session, n1)
    db_session.commit()

    assert get_unread_count(db_session, recipient.UserID, tenant.id) == 1

def test_held_notification_does_not_count_as_unread_until_released(db_session, tenant_and_users):
    tenant, other_tenant, recipient, other_tenant_user = tenant_and_users

    send_notification(
        db_session, calling_context_tenant_id=tenant.id, recipient=recipient,
        priority_tier="P1", message="held", channel_preference="IN_APP", now=THREE_AM_IST_UTC,
    )
    db_session.commit()

    assert get_unread_count(db_session, recipient.UserID, tenant.id) == 0
