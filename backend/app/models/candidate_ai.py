"""
Candidate AI Agentic Models
============================
Supports the agentic automated hiring process where an AI agent is
assigned to a candidate after they are added and assigned to a job.

Tables:
  - candidate_conversations  : The ongoing AI-managed conversation thread
                                with a candidate (one active per candidate).
  - candidate_ai_assignments  : Tracks which AI agent/persona is assigned
                                to which candidate and by whom.
  - conversation_events       : Granular event log for every action/message
                                that happens inside a conversation.

Tenant context:
  tenant_id is the users.UserID (String 50) of the HR/Admin user who owns
  this organisation — consistent with the rest of the HRMS system.
"""

import logging
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    Text, Boolean, JSON, func
)
from sqlalchemy.orm import relationship

from app.models.base import Base

# ---------------------------------------------------------------------------
# 1. candidate_conversations
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class CandidateConversation(Base):
    """
    Represents a single AI-driven conversation thread with a candidate.

    One active conversation per candidate at any given time (enforced
    at the application layer; the DB allows multiple rows so historical
    conversations are preserved).

    owner_type / owner_id:
        Polymorphic pointer to whoever currently "owns" the conversation:
        'ai_agent'  → the assigned AI agent (owner_id = ai_agent_name)
        'hr_user'   → a human HR user  (owner_id = users.UserID)

    escalation_state:
        NULL / 'none'     → no escalation
        'pending'         → waiting for HR review
        'escalated'       → handed over to HR
        'resolved'        → HR resolved and returned to AI

    channel_preference:
        'email' | 'whatsapp' | 'sms' | 'portal'
    """

    __tablename__ = "candidate_conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant — maps to users.UserID (the org owner / admin user)
    tenant_id = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )

    # The candidate this conversation belongs to
    # Candidate IDs are "CAN-" prefix + UUID (40 chars total, not 36)
    candidate_id = Column(String(512),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Conversation lifecycle status
    # e.g. 'open' | 'awaiting_candidate' | 'awaiting_hr' | 'closed' | 'escalated'
    status = Column(String(512), nullable=False, server_default="open")

    # Name / identifier of the AI agent handling this conversation
    ai_agent_name = Column(String(512), nullable=True)

    # Preferred communication channel for this conversation
    channel_preference = Column(String(512), nullable=True, server_default="email")

    # AI-generated summary of the conversation so far
    summary = Column(Text, nullable=True)

    # S-019/HRMS-0419 -- when `summary` was last (re)generated. Distinct
    # from updated_at, which also gets bumped by unrelated mutations
    # (next_action changes, status transitions) that don't touch summary.
    summary_generated_at = Column(DateTime(timezone=False), nullable=True)

    # What the AI plans to do next (e.g. "Wait for candidate reply", "Send reminder")
    next_action = Column(String(512), nullable=True)

    # Who currently owns the conversation: 'ai_agent' | 'hr_user'
    owner_type = Column(String(512), nullable=True, server_default="ai_agent")

    # ID of the current owner (ai_agent_name or users.UserID)
    owner_id = Column(String(512), nullable=True)

    # Escalation workflow state
    escalation_state = Column(String(512), nullable=True, server_default="none")

    # S-075/HRMS-0475 -- per-candidate Thunder pause. Independent of
    # owner_type (BR-01): pausing does NOT transfer ownership, so when
    # Thunder resumes it picks up where it left off with no "Hand Back"
    # required. thunder_resume_at is nullable -- NULL means "paused
    # until manually resumed" (no PauseExpiryJob auto-resume).
    is_thunder_paused = Column(Boolean, nullable=False, server_default="0")
    thunder_paused_at = Column(DateTime(timezone=False), nullable=True)
    thunder_resume_at = Column(DateTime(timezone=False), nullable=True)
    thunder_paused_by = Column(
        String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True,
    )

    # S-054/HRMS-0454 -- set true once an offer is released (Step 4).
    # Enables HRMS-0455 (Offer FAQ Bot) to respond to offer questions --
    # that story isn't built yet, but the flag is cheap, real, and
    # directly spec'd, same precedent scheduled_via_graph_event_id
    # (S-048) set before its own consumer (S-049) existed.
    offer_faq_active = Column(Boolean, nullable=False, server_default="0")

    # THUNDER REDESIGN (2026-09-04): Real engagement lifecycle tracking
    # ================================================================
    # NOTE: These columns exist in the model but not yet in the database schema.
    # They are commented out pending migration. Schema upgrade needed before use.

    # # Current engagement phase: OUTREACH | CONVERSION | DORMANT | HIRED
    # engagement_phase = Column(
    #     String(50),
    #     nullable=False,
    #     server_default="OUTREACH",
    #     index=True
    # )

    # # Knowledge level based on behavioral signals: COLD | WARM | HOT
    # knowledge_level = Column(String(50), nullable=False, server_default="COLD")

    # # When last message was sent (Day 0, 2-3, 5-7, 8-13, 14+)
    # last_touch_sent_at = Column(DateTime(timezone=False), nullable=True)

    # When next message should be sent (scheduled for future execution)
    next_touch_scheduled_at = Column(
        DateTime(timezone=False),
        nullable=True,
        index=True  # Index for efficient "get next candidates to touch" queries
    )

    # # When candidate first responded to any message
    # candidate_responded_at = Column(DateTime(timezone=False), nullable=True)

    # # Total number of times candidate has engaged (replied, clicked, opened)
    # response_count = Column(Integer, nullable=False, server_default="0")

    # # JSON tracking of behavioral signals:
    # # { opened_email: bool, clicked_link: bool, replied: bool, ... }
    # behavioral_signals = Column(JSON, nullable=True, server_default="{}")

    # # Days since candidate's last response (auto-calculated, updated daily)
    # days_since_last_response = Column(Integer, nullable=True)

    # # How many 14-day cycles have completed (0 = first cycle, 1 = second, etc.)
    # cycle_count = Column(Integer, nullable=False, server_default="0")

    # Audit timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ORM relationships
    tenant    = relationship("Users",     foreign_keys=[tenant_id],    lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    events    = relationship(
        "ConversationEvent",
        back_populates="conversation",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

# ---------------------------------------------------------------------------
# 2. candidate_ai_assignments
# ---------------------------------------------------------------------------

class CandidateAIAssignment(Base):
    """
    Records which AI agent (and persona) is assigned to a candidate.

    Multiple rows per candidate are allowed so the full assignment
    history is preserved.  Only the row where is_active=True is the
    current assignment.

    assigned_by:
        users.UserID of the HR/Admin who triggered the AI assignment
        (can also be a system user ID for automated assignments).
    """

    __tablename__ = "candidate_ai_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Tenant — maps to users.UserID
    tenant_id = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )

    # The candidate being assigned to an AI agent
    # Candidate IDs are "CAN-" prefix + UUID (50 chars)
    candidate_id = Column(String(512),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Logical name of the AI agent (e.g. "onboarding-bot", "screening-agent")
    ai_agent_name = Column(String(512), nullable=False)

    # The persona/prompt profile the agent uses for this candidate
    # (e.g. "friendly-hr", "formal-recruiter")
    # Can be quite long (e.g., full system prompt), so use Text
    ai_agent_persona = Column(Text, nullable=True)

    # When the assignment was made
    assigned_at = Column(DateTime(timezone=False), server_default=func.now())

    # Who triggered the assignment (HR user or system)
    assigned_by = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=True,
    )

    # Only one row should be True at any time (managed at application layer)
    is_active = Column(Boolean, nullable=False, server_default="1")

    # ORM relationships
    tenant    = relationship("Users",     foreign_keys=[tenant_id],    lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    assigner  = relationship("Users",     foreign_keys=[assigned_by],  lazy="select")

# ---------------------------------------------------------------------------
# 3. conversation_events
# ---------------------------------------------------------------------------

class ConversationEvent(Base):
    """
    Immutable event log for everything that happens inside a conversation.

    event_type examples:
        'ai_message_sent'       – AI sent an email / message to candidate
        'hr_message_sent'       – HR user manually sent a message (S-009)
        'candidate_reply'       – Candidate replied
        'field_check'           – AI identified missing fields
        'reminder_sent'         – Follow-up reminder dispatched
        'escalation_triggered'  – AI escalated to HR
        'hr_note_added'         – HR left a note inside the conversation
        'status_changed'        – Conversation status changed
        'ownership_changed'     – Conversation owner switched hr_user <-> ai_agent (S-010)
        'ai_assigned'           – AI agent was assigned
        'ai_deassigned'         – AI agent was removed

    event_data:
        JSON blob; schema depends on event_type.
        e.g. for 'ai_message_sent':
          { "subject": "...", "body": "...", "channel": "email", "message_id": "..." }
        e.g. for 'field_check':
          { "missing_fields": ["candidateGender", "candidateDateOfBirth"] }

    triggered_by:
        'ai_agent'  – event was raised by the AI
        'candidate' – event was raised by the candidate (e.g. reply)
        'hr_user'   – event was raised by a human HR user
        'system'    – automated system event
    """

    __tablename__ = "conversation_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # The conversation this event belongs to
    conversation_id = Column(
        Integer,
        ForeignKey("candidate_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type of event (see docstring above)
    event_type = Column(String(512), nullable=False, index=True)

    # Flexible JSON payload — structure depends on event_type
    event_data = Column(JSON, nullable=True)

    # Who or what triggered this event
    triggered_by = Column(String(512), nullable=False, server_default="ai_agent")

    # Immutable creation timestamp (events are never updated)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    # ORM relationship back to the conversation
    conversation = relationship(
        "CandidateConversation",
        foreign_keys=[conversation_id],
        back_populates="events",
    )
