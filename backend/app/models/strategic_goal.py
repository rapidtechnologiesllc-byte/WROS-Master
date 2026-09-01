"""
Strategic Goals Model

CEO sets annual goals. System automatically cascades to all departments.
Flash validation uses cascaded goals to track progress against annual targets.

Table: strategic_goals
- Stores CEO-level strategic goals for the organization
- Linked to cascaded_goals (one-to-many) for department-level targets

Table: cascaded_goals
- Auto-generated from strategic goals
- Each department/role gets their piece of the CEO goal
- Flash validation compares actual progress to cascaded goal targets
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, func, Index
from sqlalchemy.orm import relationship
from app.models.base import Base


class StrategicGoal(Base):
    """CEO-level strategic goal that cascades to all departments"""
    __tablename__ = "strategic_goals"

    id = Column(String(256), primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    goal_name = Column(String(256), nullable=False)
    goal_type = Column(String(256), nullable=False)  # "headcount", "revenue", "logos"
    target_value = Column(Float, nullable=False)
    unit = Column(String(256), nullable=False)  # "people", "$", "logos"
    year = Column(Integer, nullable=False)

    # Tracking progress
    current_value = Column(Float, default=0)
    progress_pct = Column(Float, default=0)

    # Cascade rules stored as JSON
    cascade_rules = Column(Text, nullable=True)  # JSON string with cascade configuration

    # Metadata
    created_by_user_id = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())

    # Relationships
    cascaded_goals = relationship("CascadedGoal", back_populates="strategic_goal", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_strategic_goals_tenant_year', 'tenant_id', 'year'),
        Index('idx_strategic_goals_created', 'tenant_id', 'created_at'),
    )


class CascadedGoal(Base):
    """Department/role-level goal automatically cascaded from strategic goal"""
    __tablename__ = "cascaded_goals"

    id = Column(String(256), primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    strategic_goal_id = Column(String(256), ForeignKey("strategic_goals.id"), nullable=False)

    # What department/role gets this cascade?
    cascaded_to_department = Column(String(256), nullable=False)  # "workforce_ops", "partner", "bu_head", etc.
    cascaded_to_user_id = Column(String(256), nullable=True)  # Optional: specific user if role-specific
    cascaded_to_business_unit_id = Column(String(256), nullable=True)  # Optional: scoped to specific BU

    # Cascaded target values (calculated from CEO goal)
    annual = Column(Float, nullable=False)
    quarterly = Column(Float, nullable=False)
    monthly = Column(Float, nullable=False)
    weekly = Column(Float, nullable=False)
    daily = Column(Float, nullable=False)

    # Progress tracking
    current_progress = Column(Float, default=0)
    progress_pct = Column(Float, default=0)

    # Cascade metadata
    cascade_formula = Column(String(256), nullable=True)  # "direct_assignment", "divide_equal", "divide_weighted"
    cascade_detail = Column(Text, nullable=True)  # Additional cascade information as JSON

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())

    # Relationships
    strategic_goal = relationship("StrategicGoal", back_populates="cascaded_goals")

    __table_args__ = (
        Index('idx_cascaded_goals_tenant', 'tenant_id'),
        Index('idx_cascaded_goals_strategic', 'strategic_goal_id'),
        Index('idx_cascaded_goals_dept', 'tenant_id', 'cascaded_to_department'),
        Index('idx_cascaded_goals_user', 'cascaded_to_user_id'),
    )


class PyramidReport(Base):
    """Weekly pyramid reporting records for audit and history"""
    __tablename__ = "pyramid_reports"

    id = Column(String(256), primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String(256), nullable=False)

    # Reporting context
    reporting_level = Column(String(256), nullable=False)  # "tech_lead", "manager", "architect", "bu_head", "partner", "ceo"
    reporting_week = Column(Integer, nullable=False)  # 1-52
    reporting_year = Column(Integer, nullable=False)

    # What was reported
    report_data = Column(Text, nullable=True)  # Full report as JSON

    # Flash validation results
    cascaded_goal_id = Column(String(256), ForeignKey("cascaded_goals.id"), nullable=True)
    annual_goal_value = Column(Float, nullable=True)
    year_to_date_progress = Column(Float, nullable=True)
    this_week_reported = Column(Float, nullable=True)

    # Flash analysis
    status = Column(String(256), nullable=True)  # "ON_TRACK", "SLIGHT_LAG", "CRITICAL_LAG", "AHEAD"
    flash_feedback = Column(Text, nullable=True)  # Flash's coaching/feedback
    variance = Column(Float, nullable=True)  # Variance from expected pace
    variance_pct = Column(Float, nullable=True)  # Percentage variance

    # Confirmation gate
    confirmed_accurate = Column(String(256), default="pending")  # "pending", "confirmed", "rejected"
    confirmation_comment = Column(Text, nullable=True)

    # Submission state
    submitted = Column(String(256), default="draft")  # "draft", "submitted", "rejected"
    submitted_at = Column(DateTime(timezone=False), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())

    __table_args__ = (
        Index('idx_pyramid_reports_tenant', 'tenant_id'),
        Index('idx_pyramid_reports_user', 'user_id'),
        Index('idx_pyramid_reports_week', 'reporting_year', 'reporting_week'),
        Index('idx_pyramid_reports_level', 'reporting_level'),
    )
