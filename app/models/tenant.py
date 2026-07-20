from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.models.base import Base


class Tenant(Base):
    """
    Top-level data-isolation boundary (HRMS-0109). Every business-entity
    table scopes to a tenant, resolved server-side from the authenticated
    session -- never from client input. See app/core/tenant_context.py.
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
