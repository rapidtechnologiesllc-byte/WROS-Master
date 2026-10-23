"""Message Handler: send_client_timesheet_approval

Emails the client's timesheet approver a single-use, expiring link to approve or reject one
internally approved week (client_timesheet_approval_service). Queued after the internal approval
commits (timesheet_approval_service.send_notices) or when an internal approver sends it again.

The token is issued here, so its plaintext exists only inside the email (the queue payload holds
the request id; the database holds only the SHA-256). Draft-then-send with the draft id committed
before sending: a retry re-sends the same draft and never a second link. A request that was
superseded or decided before the worker ran is skipped.

Anything that stops delivery (no Graph credentials or permission) raises DeliveryDeferred from the
mailbox, so the message stays PENDING as "not sent".

Compensation: nothing is rolled back on failure. An unsent draft stays in the mailbox's Drafts
folder and the next attempt sends that same draft; the timesheet stays CLIENT_PENDING and can be
approved with uploaded evidence meanwhile.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client_timesheet_approval import ClientTimesheetApproval
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45


class SendClientTimesheetApprovalHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        from app.services.client_timesheet_approval_service import issue_link, link_for, render_email

        request_id = (message.payload or {}).get("request_id")
        if not request_id:
            raise ValueError(f"Message {message.id} missing request_id")
        logger.info(f"[ClientTimesheetEmail] handler_start request={request_id} message={message.id}")

        # validation 1: the request exists
        request = db.query(ClientTimesheetApproval).filter(
            ClientTimesheetApproval.id == request_id).with_for_update().first()
        if request is None:
            raise ValueError(f"No client timesheet approval request {request_id}")
        # validation 2: still open (a newer request, the evidence upload or an earlier run may have closed it)
        if request.decision != "PENDING" or request.used_at is not None:
            logger.info(f"[ClientTimesheetEmail] request={request_id} is {request.decision}; not sent")
            return {"status": "superseded", "request_id": request_id}
        if request.emailed_at is not None:
            return {"status": "already_sent", "request_id": request_id}
        # validation 3: someone to send it to
        if not request.approver_email:
            raise ValueError(f"Request {request_id} has no client approver email")

        mailbox = mailbox or GraphMailbox(settings.CLIENT_TIMESHEET_APPROVAL_MAILBOX)
        if request.email_graph_id is None:
            # validation 4: content renders from real data, with a fresh link
            content = render_email(db, request, link_for(issue_link(db, request)))
            request.email_graph_id, _, _ = mailbox.create_draft(request.approver_email, content["subject"],
                                                                content["html"], f"client-timesheet:{request.id}")
            db.commit()
            logger.info(f"[ClientTimesheetEmail] drafted request={request_id} graph_id={request.email_graph_id}")
        if mailbox.is_draft(request.email_graph_id):
            mailbox.send(request.email_graph_id)
        request.emailed_at = datetime.utcnow()
        db.commit()
        logger.info(f"[ClientTimesheetEmail] handler_complete request={request_id} to={request.approver_email}")
        return {"status": "sent", "request_id": request_id, "to": request.approver_email,
                "message_sent": True, "delivery_confirmed": True}
