"""M365 OAuth session storage (one row per WROS user who connected Outlook).

Registered on the app's shared Base so initialize_database()'s
create_all() creates the table -- it previously had its own
declarative_base() and the table never existed.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.models.base import Base


class MsgraphSession(Base):
    """Delegated Microsoft Graph tokens for one WROS user's mailbox."""
    __tablename__ = "msgraph_sessions"

    user_id = Column(String(512), primary_key=True)  # Users.UserID
    account_id = Column(String(255), nullable=False, index=True)  # Microsoft account OID
    account_email = Column(String(512), nullable=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # UTC
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    mail_access = Column(Boolean, nullable=True)  # None = not checked yet
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MsgraphSession user_id={self.user_id} account_id={self.account_id}>"
