import logging
"""Pydantic schemas -- S-105/HRMS-P210 (Portal Notification Center) API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class NotificationItem(BaseModel):
    id: str
    channel: str
    priority_tier: str
    message: str
    delivery_status: str
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int
