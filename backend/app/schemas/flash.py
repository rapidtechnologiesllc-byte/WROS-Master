"""
import logging
Pydantic Schemas — Flash (internal query agent) surface.

Renamed 2026-08-06 from "Ask Thunder" -- see app.api.v1.endpoints.flash
module docstring for the Thunder-vs-Flash product split rationale.
"""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class FlashHistoryTurn(BaseModel):
    """Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
    one prior exchange from the SAME open chat panel, sent back by the
    client (FlashWidget.js already holds these in its own React
    state) so the classifier can resolve a follow-up's pronoun/
    reference -- see flash_service.classify_internal_query's
    own docstring. Not a server-side conversation store."""
    question: str = Field(..., max_length=1000)
    reply: str = Field(default="", max_length=4000)


class FlashRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: List[FlashHistoryTurn] = Field(default_factory=list, max_length=10)
    conversation_state: Optional[Dict[str, Any]] = Field(default=None, description="State tracking for multi-turn conversations like job creation")


class FlashResponse(BaseModel):
    intent: str
    reply: str
    requires_response: bool = Field(default=False, description="Whether this response expects a user response to continue")
    expected_field: Optional[str] = Field(default=None, description="Which field this response is asking for (job creation flow)")
    response_type: Optional[str] = Field(default=None, description="Type of response expected: text, boolean, select")
    conversation_state: Optional[Dict[str, Any]] = Field(default=None, description="Updated conversation state to send back to client")
    job_id: Optional[str] = Field(default=None, description="Job ID if a job was created")
