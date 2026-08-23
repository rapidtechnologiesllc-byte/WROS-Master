"""User-BusinessUnit junction table for many-to-many relationship."""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class UserBusinessUnit(Base):
    """Junction table for many-to-many relationship between Users and BusinessUnits."""
    __tablename__ = "user_business_units"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(String(50), ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("Users", foreign_keys=[user_id], back_populates="user_business_units")
    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id])

    __table_args__ = (
        # Ensure each user-BU combination is unique (composite unique constraint)
        {"uniqueConstraint": "uq_user_business_unit"},
    )
