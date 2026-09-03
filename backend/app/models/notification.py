"""
import logging
HRMS-0113 -- Notification Engine Base.

The one shared notification dispatch backbone every other story is
supposed to call instead of implementing its own send logic (per
CLAUDE.md's non-negotiables). Built for real this round after being
flagged as cited-but-not-actually-built in an earlier session round.

Not built here, and explicitly out of this story's own scope per its
"Not In Scope" section or genuinely unprovisioned in this codebase:
  - WhatsApp Business API / SMS gateway integrations -- no credentials
    exist (S-211's own prerequisites list this as required-but-not-yet-
    provisioned). The dispatch/fallback state machine around them is
    real; the actual channel senders for WHATSAPP/SMS raise
    ChannelNotConfigured by default (see notification_service.py) until
    those integrations exist. A caller can inject real senders once
    they do -- the fallback logic doesn't need to change.
  - The in-app notification bell / nav shell UI (depends on HRMS-0111,
    which doesn't exist) -- get_unread_count()/mark_as_read() in
    notification_service.py are the backend a future UI would call.
  - No message templating engine -- message content is the caller's
    responsibility, per the story's own "Not In Scope" note.
"""
import logging
import uuid

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


NOTIFICATION_CHANNELS = ("IN_APP", "EMAIL", "WHATSAPP", "SMS")
PRIORITY_TIERS = ("P0", "P1", "P2")
DELIVERY_STATUSES = ("PENDING", "SENT", "FALLBACK_SENT", "FAILED")

logger = logging.getLogger(__name__)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    recipient_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    channel = Column(
        Enum(*NOTIFICATION_CHANNELS, name="notification_channel", native_enum=False, create_constraint=True),
        nullable=False,
    )
    # Set only if BR-0113-01's P0 fallback actually fired.
    fallback_channel = Column(
        Enum(*NOTIFICATION_CHANNELS, name="notification_fallback_channel", native_enum=False, create_constraint=True),
        nullable=True,
    )
    priority_tier = Column(
        Enum(*PRIORITY_TIERS, name="notification_priority_tier", native_enum=False, create_constraint=True),
        nullable=False,
    )
    message = Column(Text, nullable=False)

    delivery_status = Column(
        Enum(*DELIVERY_STATUSES, name="notification_delivery_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    # BR-0113-03: null for P0 (always immediate); set for P1/P2 held
    # outside business hours -- the computed release time. Not cleared
    # once release actually happens, so it stays a readable audit trail
    # of "this was held until X."
    scheduled_release_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
