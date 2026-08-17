"""
RBAC Models — Roles, Permissions, Role Attributes, and Role-Permission mapping.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Role(Base):
    """A named role that can be assigned to a user."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    attributes = relationship("RoleAttribute", back_populates="role", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name!r}>"


class RoleAttribute(Base):
    """
    Behavior flags attached to a role.
    Examples: global_access, bu_restricted, pipeline_control, ...
    """
    __tablename__ = "role_attributes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name = Column(String(100), nullable=False)
    attribute_value = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    role = relationship("Role", back_populates="attributes")

    __table_args__ = (
        UniqueConstraint("role_id", "attribute_name", name="uq_role_attribute"),
    )

    def __repr__(self) -> str:
        return f"<RoleAttribute role_id={self.role_id} {self.attribute_name}={self.attribute_value}>"


class Permission(Base):
    """
    A named permission string, e.g. 'candidate.view', 'offer.approve'.
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Permission id={self.id} name={self.name!r}>"


class RolePermission(Base):
    """Many-to-many join between Role and Permission."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    def __repr__(self) -> str:
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"

# NOTE: BusinessUnit model moved to app/models/business_unit.py
# RBAC uses the BusinessUnit from business_unit which is the canonical definition
# This duplicate model is REMOVED to avoid table name conflicts with business_unit.BusinessUnit

# NOTE: Department model moved to app/models/org_structure.py
# RBAC uses the Department from org_structure which provides full organizational hierarchy support
# with hiring managers, cost centers, and multi-level org structure.
# This model is REMOVED to avoid table name conflicts with org_structure.Department