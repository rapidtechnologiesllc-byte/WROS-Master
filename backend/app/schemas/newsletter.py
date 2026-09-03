from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import logging
from datetime import datetime
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Subscriber Schemas
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class SubscriberBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    is_active: bool = True


class SubscriberCreate(SubscriberBase):
    """Payload for subscribing to the newsletter."""
    pass


class SubscriberStatusUpdate(BaseModel):
    """Payload for activating / deactivating a subscriber."""
    is_active: bool


class SubscriberResponse(SubscriberBase):
    id: int                         # Integer PK in DB — was incorrectly str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Newsletter Schemas
# ---------------------------------------------------------------------------

class NewsletterBase(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., description="HTML or plain-text body")


class NewsletterCreate(NewsletterBase):
    """Payload for creating a new newsletter draft."""
    pass


class NewsletterUpdate(BaseModel):
    """Partial payload for editing a newsletter (all fields optional)."""
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    status: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class NewsletterSchedule(BaseModel):
    """Payload for scheduling an existing newsletter."""
    scheduled_for: datetime


class NewsletterResponse(NewsletterBase):
    id: str
    status: str
    created_by: str
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NewsletterSendResult(BaseModel):
    """Response returned after an immediate send."""
    newsletter_id: str
    recipients_count: int
    message: str
