"""
S-205/HRMS-0107 -- Business Unit Entity & Context Switching.

bu_access is the real junction table the spec asks for (user_id,
business_unit_id, is_default) -- BusinessUnit model is defined in
app.models.business_unit. Default: one row per user matching
their home BU (Users.business_unit_id); cross-BU users get multiple
rows, seeded/managed via the API this story adds, not automatically
inferred beyond that one default row.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint

from app.models.base import Base


class BUAccess(Base):
    __tablename__ = "bu_access"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.UserID"), nullable=False, index=True)
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=False, index=True)
    is_default = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "bu_context_id", name="uq_bu_access_user_bu"),
    )
