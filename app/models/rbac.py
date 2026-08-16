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

class BusinessUnit(Base):
    """A business unit (BU) that users can belong to. BU is independent."""
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    # HRMS-0109 — nullable for the same safe-upgrade reason as elsewhere.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # HRMS-0101 — extends the existing table rather than creating a second
    # business_units table (the requirements doc specced one fresh, but
    # this one already exists and is in active use by RBAC).
    bu_code = Column(String(50), nullable=True)
    parent_bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    bu_head_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True, index=True)
    # 2026-08-06, confirmed directly with Avinash -- symmetric to
    # bu_head_employee_id above. One designated HR person per BU, so
    # Job creation can auto-resolve both from the selected client's BU
    # instead of a manual assignment step (agentic-first mandate).
    hr_manager_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True, index=True)
    # S-205/HRMS-0107 -- extends this existing table rather than
    # forking a second one, same "extend, don't fork" convention as
    # bu_code/parent_bu_id above. continent drives HRMS-0121's default
    # locale/currency per the spec's own UI Fields note -- plain
    # String, same no-native-DB-enum convention Project.continent
    # already uses, not a formal constrained value set.
    continent = Column(String(50), nullable=True)
    region = Column(String(60), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Back-reference: all departments that belong to this BU
    # NOTE: Uses Department from app.models.org_structure (consolidated to avoid duplicate tables)
    departments = relationship("Department", foreign_keys="Department.business_unit_id", lazy="select")
    parent_bu = relationship("BusinessUnit", remote_side=[id], foreign_keys=[parent_bu_id])

    def __repr__(self) -> str:
        return f"<BusinessUnit id={self.id} name={self.name!r}>"


# NOTE: Department model moved to app/models/org_structure.py
# RBAC uses the Department from org_structure which provides full organizational hierarchy support
# with hiring managers, cost centers, and multi-level org structure.
# This model is REMOVED to avoid table name conflicts with org_structure.Department