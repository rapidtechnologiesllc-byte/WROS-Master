"""
Flash — Internal Query Agent — API Endpoints
=======================================
Prefix: /flash
import logging
Tag:    flash

Real, authenticated conversational query surface for BlitzenX staff and
employees. 2026-08-06, Avinash's explicit product split: Thunder is the
EXTERNAL-facing agent (open jobs, a logged-in candidate's own
application/onboarding status) -- Flash is the INTERNAL-facing agent,
used by staff and by anyone once they convert from candidate to
employee. See app.services.flash_service for the full rationale: every
answer comes from a real DB query, never a fabricated one; the LLM
only classifies intent and extracts a search term -- "strict mode,"
per Avinash's own words, not a general-purpose chat model guessing.

Renamed 2026-08-06 from "Ask Thunder" (module/route prefix were
internal_ask_thunder.py / /ask-thunder) -- functionally unchanged,
this is a branding/naming correction only. Git history preserved via
`git mv`.

Gated the same way app.api.v1.endpoints.clients is (get_current_internal_user)
-- this system has no dedicated BU Head / Resource Manager role yet
(see src/layout/Shell.js's own note on this), so the broad internal-
staff check is the closest real gate available today. Individual
intents (finance_pnl, ar_aging) apply a stricter, additional gate on
top of this (see flash_service.can_view_pnl) for financial data
specifically.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.schemas.flash import FlashRequest, FlashResponse
from app.services.flash_service import answer_internal_query

router = APIRouter(prefix="/flash", tags=["flash"])

@router.post(
    "/",
    dependencies=[Depends(get_current_internal_user)],
    response_model=FlashResponse,
    summary="Ask Flash an operational question — real data, no hallucinated answers",
)
def ask_flash(
    body: FlashRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    history = [{"question": turn.question, "reply": turn.reply} for turn in body.history]
    result = answer_internal_query(
        db,
        body.message,
        current_user=current_user,
        history=history,
        conversation_state=body.conversation_state
    )
    return FlashResponse(**result)
