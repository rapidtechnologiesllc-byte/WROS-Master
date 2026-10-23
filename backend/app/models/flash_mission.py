"""Flash missions (flash spec D): after a job is created in the Flash chat, Flash keeps working it
-- bench first, then sourcing, interview scheduling and feedback chasing -- until every position is
filled by a candidate who has JOINED (CEO 2026-10-15), and reports progress in the requester's
conversation. app.services.flash_mission_service runs it from the flash_mission_sweep job.

One track (FlashMissionCandidate) per candidate: PROPOSED -> SCHEDULED -> AWAITING_VERDICT ->
(AWAITING_HUMAN | ROUND_PASSED -> SCHEDULED | OFFER_PENDING -> FILLED | FAILED), or SKIPPED /
WITHDRAWN. Flash reads verdicts, offers and joining; people record them."""
import uuid

from sqlalchemy import (JSON, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)

from app.models.base import Base

MISSION_STATES = ("AWAITING_JOB", "ACTIVE", "BLOCKED", "PAUSED", "CLOSED", "CANCELLED", "FAILED")
SWEPT_STATES = ("AWAITING_JOB", "ACTIVE", "BLOCKED")
BLOCK_REASONS = ("no_interviewer", "no_slot", "permission", "owner_inactive")
TRACK_STATUSES = ("PROPOSED", "SCHEDULED", "AWAITING_VERDICT", "AWAITING_HUMAN", "ROUND_PASSED", "OFFER_PENDING",
                  "FILLED", "FAILED", "SKIPPED", "WITHDRAWN")
# Tracks still in interviews: they count against the parallel cap (offers do not -- CEO 2026-10-15)
INTERVIEWING = ("PROPOSED", "SCHEDULED", "AWAITING_VERDICT", "AWAITING_HUMAN", "ROUND_PASSED")


class FlashMission(Base):
    __tablename__ = "flash_missions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    # No FK: the mission is created while job_created_flash is still queued; the sweep checks it
    job_id = Column(String(512), nullable=False, unique=True)
    requested_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("flash_conversations.id", ondelete="SET NULL"), nullable=True)
    state = Column(Enum(*MISSION_STATES, name="flash_mission_state", native_enum=False, create_constraint=True),
                   nullable=False, default="AWAITING_JOB")
    block_reason = Column(String(40), nullable=True)
    blocked_since = Column(DateTime, nullable=True)
    state_reason = Column(Text, nullable=True)
    positions = Column(Integer, nullable=False)
    next_check_at = Column(DateTime, nullable=False, index=True)
    last_progress_at = Column(DateTime, nullable=True)
    escalation_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    escalation_count = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime, nullable=True)
    block_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    consecutive_errors = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_flash_missions_state_next_check", "state", "next_check_at"),)


class FlashMissionCandidate(Base):
    __tablename__ = "flash_mission_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(String(36), ForeignKey("flash_missions.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    status = Column(Enum(*TRACK_STATUSES, name="flash_mission_track_status", native_enum=False,
                         create_constraint=True), nullable=False, default="PROPOSED")
    level = Column(String(10), nullable=True)
    score = Column(Integer, nullable=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id", ondelete="SET NULL"), nullable=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="SET NULL"), nullable=True)
    interviewer_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    feedback_chases = Column(Integer, nullable=False, default=0)
    last_chased_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("mission_id", "candidate_id", name="uq_flash_mission_candidate"),)


class FlashMissionEvent(Base):
    """What happened on a mission, in order (feeds "status of my search")."""
    __tablename__ = "flash_mission_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(String(36), ForeignKey("flash_missions.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(40), nullable=False)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_flash_mission_events_mission_id_id", "mission_id", "id"),)
