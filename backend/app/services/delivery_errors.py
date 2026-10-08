from datetime import datetime, timedelta
from typing import Optional

DEFAULT_DEFER_MINUTES = 15


class DeliveryDeferred(RuntimeError):
    """The message was NOT sent and must stay PENDING (not failed, not completed)
    until retry_at: delivery not configured, permission missing, outside the
    send window, or over a send cap. Never counts toward retry exhaustion."""

    def __init__(self, reason: str, retry_at: Optional[datetime] = None):
        super().__init__(reason)
        self.reason = reason
        self.retry_at = retry_at or datetime.utcnow() + timedelta(minutes=DEFAULT_DEFER_MINUTES)
