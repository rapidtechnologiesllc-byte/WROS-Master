"""M365 OAuth session storage (database-backed for persistence)."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MsgraphSession(Base):
    """Stores M365 OAuth tokens for mail sync (persists across server restarts)."""
    __tablename__ = "msgraph_sessions"

    user_id = Column(String(255), primary_key=True)  # app.models.user.Users.UserID
    account_id = Column(String(255), unique=True)  # Microsoft account OID
    access_token = Column(String(2000))  # JWT token
    refresh_token = Column(String(2000))  # Refresh token
    expires_at = Column(DateTime)  # Token expiration
    is_active = Column(Boolean, default=True)  # Soft delete
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_msgraph_active", "is_active"),
        Index("idx_msgraph_account", "account_id"),
    )

    def __repr__(self):
        return f"<MsgraphSession user_id={self.user_id} account_id={self.account_id}>"
