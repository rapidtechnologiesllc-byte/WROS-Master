"""
S-356/HRMS-0517 -- Employee Milestone Tracker: Personal, Project & Org.

Named `employee_milestones` (table + model), deliberately distinct from
the already-shipped `project_milestones`/`ProjectMilestone`
(HRMS-0801/0804, built earlier this session as part of the Projects
API) even though this story's own doc names its table `project_
milestones` too -- a real table-name collision between two stories,
not a drift to silently paper over. The two are genuinely different
entities: ProjectMilestone is project-scoped only, a binary PENDING/
COMPLETE, and has no performance-store integration. This story is a
three-tier PERSONAL/PROJECT/ORG tracker whose completions and overdue
detections auto-write to employee_performance_events (HRMS-0515) and
feed the Core Eligibility AI Assessor (HRMS-0518). Extending the
existing table to match this doc's richer schema would mean migrating
two enum-shaped columns (is_complete -> status) on a table the
already-shipped Projects API (POST/GET /projects/{id}/milestones) is
built against and tested -- a real, avoidable break for something that
is conceptually a different feature. Flagged, not guessed at.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func

from app.models.base import Base

MILESTONE_TYPES = ("PERSONAL", "PROJECT", "ORG")
MILESTONE_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "OVERDUE", "CANCELLED", "EXTENDED")
OPEN_MILESTONE_STATUSES = ("PENDING", "IN_PROGRESS")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class EmployeeMilestone(Base):
    __tablename__ = "employee_milestones"

    id = Column(String(256), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Nullable per the doc's own note: null for PERSONAL/ORG (no project
    # tie), null for PROJECT-level on employee_id (a project checkpoint
    # isn't owned by one person).
    project_id = Column(String(256), ForeignKey("projects.id"), nullable=True, index=True)
    employee_id = Column(String(256), ForeignKey("employees.id"), nullable=True, index=True)

    milestone_type = Column(
        Enum(*MILESTONE_TYPES, name="employee_milestone_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(Date, nullable=False)
    # BR: system-set to CURRENT_DATE at the completion API call, never a
    # caller-supplied value -- enforced in the service layer, not here.
    completed_date = Column(Date, nullable=True)
    status = Column(
        Enum(*MILESTONE_STATUSES, name="employee_milestone_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    completion_notes = Column(Text, nullable=True)
    set_by = Column(String(256), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
