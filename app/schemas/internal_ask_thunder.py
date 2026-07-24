"""
Pydantic Schemas — internal "Ask Thunder" query surface.
"""

from pydantic import BaseModel, Field


class AskThunderRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class AskThunderResponse(BaseModel):
    intent: str
    reply: str
