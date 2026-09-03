"""
import logging
S-324/HRMS-ONBOARDING-WORKFLOW -- Onboarding Workflow Management.

onboarding_workflow: tracks the onboarding lifecycle for new employees.
onboarding_buddy: assigns a buddy to guide the new employee.
onboarding_task: tracks assigned onboarding tasks and training.

This model manages the full onboarding journey after an employee joins,
including buddy assignment, welcome kit delivery, and training scheduling.
"""
import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum, UniqueConstraint, func, Date
from sqlalchemy.orm import relationship

from app.models.base import Base

ONBOARDING_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "COMPLETED", "ON_HOLD", "DEFERRED")
BUDDY_STATUSES = ("ASSIGNED", "ACTIVE", "COMPLETED", "DECLINED", "UNAVAILABLE")
TASK_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED", "DEFERRED")
TASK_TYPES = ("ORIENTATION", "TRAINING", "DOCUMENTATION", "SYSTEM_ACCESS", "TEAM_INTRODUCTION", "CUSTOM")
WELCOME_KIT_TYPES = ("EMAIL", "PHYSICAL", "DIGITAL", "HYBRID")
TRAINING_STATUS = ("SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "RESCHEDULED")

logger = logging.getLogger(__name__)

class OnboardingWorkflow(Base):
    """Main onboarding workflow record for an employee."""
    __tablename__ = "onboarding_workflows"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=True)

    # Workflow state
    status = Column(
        Enum(*ONBOARDING_STATUSES, name="onboarding_workflow_status", native_enum=False, create_constraint=True),
        nullable=False, server_default="NOT_STARTED",
    )

    # Onboarding timeline
    joining_date = Column(Date, nullable=False, index=True)
    onboarding_start_date = Column(Date, nullable=True)
    onboarding_end_date = Column(Date, nullable=True)
    expected_completion_date = Column(Date, nullable=True)  # D+30, D+90 based on role

    # Assignment information
    assigned_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    reporting_manager_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)

    # Progress tracking
    total_tasks = Column(Integer, nullable=False, server_default="0")
    completed_tasks = Column(Integer, nullable=False, server_default="0")
    progress_percentage = Column(Integer, nullable=False, server_default="0")

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=False), nullable=True)

    # Relationships
    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    employee = relationship("Employee", foreign_keys=[employee_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    assigned_by_user = relationship("Users", foreign_keys=[assigned_by_user_id], lazy="select")
    reporting_manager = relationship("Users", foreign_keys=[reporting_manager_id], lazy="select")
    buddy = relationship("OnboardingBuddy", uselist=False, back_populates="workflow", cascade="all, delete-orphan")
    tasks = relationship("OnboardingTask", back_populates="workflow", cascade="all, delete-orphan")
    welcome_kits = relationship("WelcomeKit", back_populates="workflow", cascade="all, delete-orphan")
    training_sessions = relationship("TrainingSession", back_populates="workflow", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_onboarding_workflow_employee"),
    )


class OnboardingBuddy(Base):
    """Buddy assignment for onboarding."""
    __tablename__ = "onboarding_buddies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("onboarding_workflows.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    buddy_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    # Buddy information
    buddy_department = Column(String(512), nullable=True)
    buddy_experience_level = Column(String(512), nullable=True)  # JUNIOR, MID, SENIOR, LEAD

    # Status and timeline
    status = Column(
        Enum(*BUDDY_STATUSES, name="onboarding_buddy_status", native_enum=False, create_constraint=True),
        nullable=False, server_default="ASSIGNED",
    )

    assigned_at = Column(DateTime(timezone=False), server_default=func.now())
    activation_date = Column(Date, nullable=True)  # When buddy officially starts guiding
    completion_date = Column(Date, nullable=True)

    # Interaction tracking
    check_ins_scheduled = Column(Integer, nullable=False, server_default="0")
    check_ins_completed = Column(Integer, nullable=False, server_default="0")
    last_interaction_date = Column(DateTime(timezone=False), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    workflow = relationship("OnboardingWorkflow", back_populates="buddy", foreign_keys=[workflow_id])
    buddy_user = relationship("Users", foreign_keys=[buddy_user_id], lazy="select")
    employee = relationship("Employee", foreign_keys=[employee_id], lazy="select")


class WelcomeKit(Base):
    """Welcome kit/materials distribution tracking."""
    __tablename__ = "welcome_kits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("onboarding_workflows.id", ondelete="CASCADE"), nullable=False, index=True)

    kit_type = Column(
        Enum(*WELCOME_KIT_TYPES, name="welcome_kit_type", native_enum=False, create_constraint=True),
        nullable=False,
    )

    # Kit contents
    kit_name = Column(String(512), nullable=False)  # e.g., "Day 1 Welcome Package"
    kit_description = Column(Text, nullable=True)
    kit_contents = Column(Text, nullable=True)  # JSON-formatted list of items

    # Delivery information
    sent_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    sent_date = Column(DateTime(timezone=False), nullable=True)
    sent_channel = Column(String(512), nullable=True)  # EMAIL, PHYSICAL_MAIL, SMS, IN_PERSON

    # Delivery status
    delivery_status = Column(String(512), nullable=False, server_default="PENDING")  # PENDING, SENT, DELIVERED, FAILED, ACKNOWLEDGED
    delivery_date = Column(DateTime(timezone=False), nullable=True)
    acknowledgement_date = Column(DateTime(timezone=False), nullable=True)

    # Tracking
    tracking_number = Column(String(512), nullable=True)  # For physical mail
    recipient_email = Column(String(512), nullable=True)
    recipient_phone = Column(String(20), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    workflow = relationship("OnboardingWorkflow", back_populates="welcome_kits", foreign_keys=[workflow_id])
    sent_by_user = relationship("Users", foreign_keys=[sent_by_user_id], lazy="select")


class TrainingSession(Base):
    """Training session scheduling and tracking."""
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("onboarding_workflows.id", ondelete="CASCADE"), nullable=False, index=True)

    # Training details
    training_name = Column(String(512), nullable=False)
    training_description = Column(Text, nullable=True)
    training_type = Column(String(512), nullable=True)  # MANDATORY, OPTIONAL, ROLE_SPECIFIC

    # Scheduling
    scheduled_date = Column(Date, nullable=False, index=True)
    scheduled_time = Column(String(10), nullable=False)  # HH:MM format
    duration_minutes = Column(Integer, nullable=True, server_default="60")
    timezone = Column(String(64), nullable=False, server_default="Asia/Kolkata")

    # Trainer/facilitator
    trainer_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    trainer_name = Column(String(512), nullable=True)
    trainer_email = Column(String(512), nullable=True)

    # Delivery mode
    delivery_mode = Column(String(512), nullable=False, server_default="IN_PERSON")  # IN_PERSON, VIRTUAL, HYBRID, SELF_PACED

    # Meeting details (for virtual sessions)
    meeting_link = Column(String(512), nullable=True)
    meeting_platform = Column(String(512), nullable=True)  # ZOOM, TEAMS, GOOGLE_MEET, etc.

    # Status and completion
    status = Column(
        Enum(*TRAINING_STATUS, name="training_session_status", native_enum=False, create_constraint=True),
        nullable=False, server_default="SCHEDULED",
    )

    # Attendance tracking
    attendance_status = Column(String(512), nullable=True)  # ATTENDED, ABSENT, EXCUSED, RESCHEDULED
    actual_start_time = Column(DateTime(timezone=False), nullable=True)
    actual_end_time = Column(DateTime(timezone=False), nullable=True)

    # Completion
    completed_date = Column(DateTime(timezone=False), nullable=True)
    feedback_received = Column(Boolean, nullable=False, server_default="0")
    feedback_score = Column(Integer, nullable=True)  # 1-5 rating
    feedback_notes = Column(Text, nullable=True)

    # Metadata
    calendar_invite_sent = Column(Boolean, nullable=False, server_default="0")
    reminder_sent = Column(Boolean, nullable=False, server_default="0")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    workflow = relationship("OnboardingWorkflow", back_populates="training_sessions", foreign_keys=[workflow_id])
    trainer_user = relationship("Users", foreign_keys=[trainer_user_id], lazy="select")


class OnboardingTask(Base):
    """Individual onboarding tasks to be completed."""
    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("onboarding_workflows.id", ondelete="CASCADE"), nullable=False, index=True)

    # Task details
    task_type = Column(
        Enum(*TASK_TYPES, name="onboarding_task_type", native_enum=False, create_constraint=True),
        nullable=False,
    )

    task_name = Column(String(512), nullable=False)
    task_description = Column(Text, nullable=True)
    task_priority = Column(String(512), nullable=False, server_default="MEDIUM")  # HIGH, MEDIUM, LOW

    # Assignment
    assigned_to_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    assigned_by_user_id = Column(String(512), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)
    assigned_date = Column(DateTime(timezone=False), server_default=func.now())

    # Timeline
    due_date = Column(Date, nullable=True, index=True)
    start_date = Column(Date, nullable=True)
    completion_target_days = Column(Integer, nullable=True)  # Days from joining date

    # Status tracking
    status = Column(
        Enum(*TASK_STATUSES, name="onboarding_task_status", native_enum=False, create_constraint=True),
        nullable=False, server_default="PENDING",
    )

    started_date = Column(DateTime(timezone=False), nullable=True)
    completed_date = Column(DateTime(timezone=False), nullable=True)

    # Task completion
    completion_notes = Column(Text, nullable=True)
    completion_proof = Column(Text, nullable=True)  # URL or reference to proof

    # Dependencies
    depends_on_task_id = Column(Integer, ForeignKey("onboarding_tasks.id", ondelete="SET NULL"), nullable=True)

    # Metadata
    is_mandatory = Column(Boolean, nullable=False, server_default="1")
    is_system_generated = Column(Boolean, nullable=False, server_default="0")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    workflow = relationship("OnboardingWorkflow", back_populates="tasks", foreign_keys=[workflow_id])
    assigned_to_user = relationship("Users", foreign_keys=[assigned_to_user_id], lazy="select")
    assigned_by_user = relationship("Users", foreign_keys=[assigned_by_user_id], lazy="select")
