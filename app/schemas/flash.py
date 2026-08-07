"""
Pydantic Schemas — Flash (internal query agent) surface.

Renamed 2026-08-06 from "Ask Thunder" -- see app.api.v1.endpoints.flash
module docstring for the Thunder-vs-Flash product split rationale.
"""

from typing import List

from pydantic import BaseModel, Field


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


class FlashResponse(BaseModel):
    intent: str
    reply: str
