"""One-time codes of the Microsoft sign-in that were already exchanged for a session (app.api.v1.endpoints.auth
microsoft_exchange): a code can be used once. Rows older than the code's two-minute life are never needed again."""
from sqlalchemy import Column, DateTime, String, func

from app.models.base import Base


class UsedSignInCode(Base):
    __tablename__ = "used_sign_in_codes"

    jti = Column(String(64), primary_key=True)
    user_id = Column(String(512), nullable=False, index=True)
    used_at = Column(DateTime, nullable=False, server_default=func.now())
