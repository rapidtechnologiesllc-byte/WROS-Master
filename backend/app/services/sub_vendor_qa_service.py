from app.core.logging import logger
"""HRMS-P814 -- Sub-Vendor Request for Clarification."""
from datetime import datetime
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.sub_vendor import ClarificationQA, SubVendorAccount, SubVendorRequest

MIN_QUESTION_LENGTH = 10
MIN_ANSWER_LENGTH = 10

logger = logging.getLogger(__name__)

class ClarificationValidationError(Exception):
    pass

def ask_question(
    db: Session, request: SubVendorRequest, sub_vendor: SubVendorAccount, *, question: str,
    tenant_id: Optional[int] = None,
) -> ClarificationQA:
    if len(question or "") < MIN_QUESTION_LENGTH:
        raise ClarificationValidationError(f"Question must be at least {MIN_QUESTION_LENGTH} characters.")

    qa = ClarificationQA(
        tenant_id=tenant_id or request.tenant_id, request_id=request.id,
        sub_vendor_id=sub_vendor.id, question=question,
    )
    db.add(qa)
    return qa

def answer_question(db: Session, qa: ClarificationQA, *, answered_by: str, answer: str) -> ClarificationQA:
    if len(answer or "") < MIN_ANSWER_LENGTH:
        raise ClarificationValidationError(f"Answer must be at least {MIN_ANSWER_LENGTH} characters.")

    qa.answer = answer
    qa.answered_by = answered_by
    qa.answered_at = datetime.utcnow()
    db.add(qa)
    return qa

def get_qa_for_request(db: Session, request: SubVendorRequest) -> List[ClarificationQA]:
    """
    HRMS-P814 BR-0814-01: visible to every vendor viewing this request,
    not just the one who asked -- no sub_vendor_id filter here, unlike
    get_submissions_for_vendor()'s isolation boundary. This IS the
    shared-visibility behavior, not an oversight.
    """
    return db.query(ClarificationQA).filter(
        ClarificationQA.request_id == request.id
    ).order_by(ClarificationQA.asked_at.asc()).all()
