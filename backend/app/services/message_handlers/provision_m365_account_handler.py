"""Message Handler: provision_m365_account

Creates the new employee's Microsoft 365 account (when it does not exist) and opens one IT Admin task to
license it (app.services.m365_account_service). Microsoft Graph not configured, or answering 5xx / 429,
raises DeliveryDeferred: the message stays PENDING and is retried, never marked done without an answer.

Compensation: none; every step is idempotent (the account is looked up by its email before it is created,
and there is at most one open task per person and category).
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.user import Users
from app.services.delivery_errors import DeliveryDeferred
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 40
RETRY_MINUTES = 30


class ProvisionM365AccountHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, graph=None) -> Dict[str, Any]:
        from app.services import m365_account_service as m365

        user_id = (message.payload or {}).get("user_id")
        if not user_id:
            raise ValueError(f"Message {message.id} missing user_id")
        logger.info(f"[M365] handler_start user={user_id}")
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None:
            raise ValueError(f"User {user_id} not found")
        if graph is None and not m365.graph_configured():
            raise DeliveryDeferred("Microsoft Graph is not configured (TENANT_ID, CLIENT_ID, CLIENT_SECRET)",
                                   datetime.utcnow() + timedelta(minutes=RETRY_MINUTES))
        try:
            result = m365.provision(db, user, graph)
        except m365.GraphError as exc:
            raise DeliveryDeferred(f"Microsoft did not answer: {exc}",
                                   datetime.utcnow() + timedelta(minutes=RETRY_MINUTES)) from exc
        db.commit()
        m365.notify_new_tasks(db)
        logger.info(f"[M365] handler_complete user={user_id} status={result['status']}")
        return {"user_id": user_id, **result}
