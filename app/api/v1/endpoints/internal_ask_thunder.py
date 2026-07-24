"""
Internal Ask Thunder — API Endpoints
=======================================
Prefix: /ask-thunder
Tag:    ask-thunder

Real, authenticated conversational query surface for BlitzenX staff --
a recruiter sourcing candidates for a role, a BU head checking a named
candidate's status, a resource manager asking for a candidate. See
app.services.internal_ask_thunder_service for the full rationale:
every answer comes from a real DB query, never a fabricated one; the
LLM only classifies intent and extracts a search term.

Gated the same way app.api.v1.endpoints.clients is (get_current_hr_or_admin)
-- this system has no dedicated BU Head / Resource Manager role yet
(see src/layout/Shell.js's own note on this), so the broad internal-
staff check is the closest real gate available today.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.schemas.internal_ask_thunder import AskThunderRequest, AskThunderResponse
from app.services.internal_ask_thunder_service import answer_internal_query

router = APIRouter(prefix="/ask-thunder", tags=["ask-thunder"])


@router.post(
    "/",
    response_model=AskThunderResponse,
    summary="Ask Thunder an operational question — real data, no hallucinated answers",
)
def ask_thunder(
    body: AskThunderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    result = answer_internal_query(db, body.message)
    return AskThunderResponse(**result)
