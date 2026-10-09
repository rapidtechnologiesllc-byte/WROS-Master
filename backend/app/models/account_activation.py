from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base


class AccountActivationToken(Base):
    """A single-use link that lets a person set their own password: sent when an
    employee account is created (activation) or on request (forgot password).
    Only the SHA-256 of the token is stored."""
    __tablename__ = "account_activation_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(512), ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    purpose = Column(String(16), nullable=False, default="ACTIVATE")  # ACTIVATE / RESET
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    email_graph_id = Column(String(512), nullable=True)  # draft id: a retry re-sends the same draft
    emailed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
