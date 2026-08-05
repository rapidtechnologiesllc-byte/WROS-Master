"""
Pydantic Schemas — internal "Ask Thunder" query surface.
"""

from typing import List

from pydantic import BaseModel, Field


class AskThunderHistoryTurn(BaseModel):
    """Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
    one prior exchange from the SAME open chat panel, sent back by the
    client (AskThunderWidget.js already holds these in its own React
    state) so the classifier can resolve a follow-up's pronoun/
    reference -- see internal_ask_thunder_service.classify_internal_query's
    own docstring. Not a server-side conversation store."""
    question: str = Field(..., max_length=1000)
    reply: str = Field(default="", max_length=4000)


class AskThunderRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: List[AskThunderHistoryTurn] = Field(default_factory=list, max_length=10)


class AskThunderResponse(BaseModel):
    intent: str
    reply: str
