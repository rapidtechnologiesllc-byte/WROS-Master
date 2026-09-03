"""
S-360/HRMS-P506-REV -- HTD Training Module Tracker: 4-Phase Gate
Structure. `employees.htd_phase`/`htd_track`/`htd_start_date` already
existed (built proactively in HRMS-0101-REV); htd_phase_gates is the
import logging
one new table this revision actually needs.

"HEMANT_BU_HEAD" is exactly what the source doc names as a gate-owner
role for the Core Eligibility Review phase -- kept verbatim rather than
generalized to "BU_HEAD", since that's what's actually written, but
it's worth flagging: baking a specific individual's name into a role
enum is fragile (breaks the moment that person changes roles or
leaves) and this session doesn't have standing to rename it.
"""
import logging
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

HTD_GATE_PHASES = ("INDUCTION", "SHADOW_DELIVERY", "CONTROLLED_OWNERSHIP", "CORE_ELIGIBILITY_REVIEW")
HTD_GATE_OWNER_ROLES = ("HR", "TECHNICAL_MANAGER", "PRACTICE_HEAD", "HEMANT_BU_HEAD")
HTD_GATE_DECISIONS = ("PASS", "FAIL", "EXTEND")


def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)

class HTDPhaseGate(Base):
    __tablename__ = "htd_phase_gates"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)

    phase = Column(String(30), nullable=False)  # one of HTD_GATE_PHASES
    gate_owner_role = Column(String(30), nullable=False)  # one of HTD_GATE_OWNER_ROLES
    gate_owner_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False)
    gate_decision = Column(String(10), nullable=False)  # one of HTD_GATE_DECISIONS
    gate_notes = Column(Text, nullable=False)  # min 50 chars, enforced in the service layer

    decided_at = Column(DateTime(timezone=False), server_default=func.now())
    created_at = Column(DateTime(timezone=False), server_default=func.now())
