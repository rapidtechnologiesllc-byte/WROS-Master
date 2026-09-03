"""
import logging
S-031/HRMS-0431 -- AI Prompt Framework.

prompt_execution_log: a genuinely new table -- an LLM-call audit
record (tokens, latency, model, success/failure) doesn't fit
ConversationEvent's shape (which is candidate-conversation-scoped;
this needs to work even for candidate_id=None calls like
INTENT_DETECTION classification runs that aren't necessarily tied to
a stored conversation event). Integer-PK + String(50) UserID-as-
tenant_id convention, matching every other new table this round.

BR-03: candidate_id is nullable (some prompt types, e.g. a general
classification call, may not have one); tenant_id is not, per the
spec's own real requirement that every call be attributable.
"""
import logging
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class PromptExecutionLog(Base):
    __tablename__ = "prompt_execution_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="SET NULL"), nullable=True, index=True)

    prompt_type = Column(String(512), nullable=False)
    template_version = Column(String(20), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    response_preview = Column(String(512), nullable=True)
    model = Column(String(512), nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
