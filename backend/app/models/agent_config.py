"""
import logging
Agent Configuration Model - Defines configurable agent pipeline settings.

An AgentConfig represents a single agent in the system and its orchestration settings.
Used by Flash Orchestrator to dynamically route candidates through the pipeline.

Fields:
- name: Unique identifier (e.g., "thunder", "recruitment_screener", "interview_scheduler")
- display_name: User-friendly name (e.g., "AI Recruiter", "Screening Bot")
- description: What this agent does in the pipeline
- queue_name: Input queue for this agent (messages from previous agent)
- next_queue_name: Output queue routed to next agent
- enabled: Whether this agent is active in the pipeline
- order: Sequence in pipeline (1=first, 2=second, etc.)
- tenant_id: For multi-tenancy support
- created_at, updated_at: Audit timestamps
"""

from sqlalchemy import Column, String, Boolean, Integer, DateTime, UUID, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base

logger = logging.getLogger(__name__)

class AgentConfig(Base):
    """
    Agent Configuration Table

    Stores the configuration for each agent in the pipeline.
    When a new agent config is created or updated, permissions are auto-synced
    to ensure the "agents" resource has proper access control.
    """
    __tablename__ = "agent_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Agent Identity
    name = Column(String(512), nullable=False, unique=True)  # Unique key: "thunder", "recruitment_screener"
    display_name = Column(String(512), nullable=False)  # "AI Recruiter", "Screening Bot"
    description = Column(Text, nullable=True)  # What does this agent do?

    # Queue Configuration
    queue_name = Column(String(512), nullable=False)  # Input queue for this agent
    next_queue_name = Column(String(512), nullable=True)  # Output queue to next agent

    # Pipeline Status
    enabled = Column(Boolean, default=True)  # Is this agent active?
    order = Column(Integer, nullable=False)  # Sequence in pipeline (1, 2, 3...)

    # Tenancy & Audit
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AgentConfig {self.name} (order={self.order}, enabled={self.enabled})>"
