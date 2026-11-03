"""Which mailbox an outbound email is drafted in (CEO 2026-11-03: "all emails should be sent by the user
logged in and not helpdesk_hrms. Helpdesk is ... a repository").

An email goes from a person's own Outlook when they have connected it (delegated Mail.Send /
Mail.ReadWrite), with the helpdesk mailbox copied; otherwise from the helpdesk mailbox as before.
The choice is made once, at the first send attempt, and kept here so every retry re-sends the draft
in the mailbox that holds it. internet_message_id lets the helpdesk poller recognise its copy of
an email we sent (it is ours, never a forward or a reply). Thunder's candidate emails keep the
same facts on ThunderEmailMessage (mailbox, internet_message_id).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class OutboundEmailSender(Base):
    __tablename__ = "outbound_email_senders"

    key = Column(String(255), primary_key=True)  # e.g. "staff:<queue message id>"
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    mailbox = Column(String(320), nullable=False)
    sender_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    internet_message_id = Column(String(998), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
