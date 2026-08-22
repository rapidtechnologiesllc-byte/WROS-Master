"""HRMS-0513 (S-352) — Core Eligibility Gate — Performance Gate Workflow"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session


def initiate_core_eligibility_review(db: Session, employee_id: str, initiated_by_user_id: str):
    """Initiate core eligibility review for employee."""
    return {
        "review_id": f"review_{employee_id}_{datetime.utcnow().timestamp()}",
        "employee_id": employee_id,
        "status": "AI_PENDING",
        "initiated_at": datetime.utcnow().isoformat(),
    }


def submit_rm_recommendation(db: Session, review_id: str, recommendation: str, notes: str):
    """RM submits recommendation for core eligibility review."""
    return {
        "review_id": review_id,
        "status": "BU_HEAD_REVIEW",
        "rm_recommendation": recommendation,
        "rm_notes": notes,
        "updated_at": datetime.utcnow().isoformat(),
    }


def submit_bu_head_decision(db: Session, review_id: str, decision: str, notes: str):
    """BU Head makes final decision on core eligibility."""
    return {
        "review_id": review_id,
        "status": decision.upper(),
        "bu_head_decision": decision,
        "bu_head_notes": notes,
        "updated_at": datetime.utcnow().isoformat(),
    }


def get_core_eligibility_review(db: Session, review_id: str):
    """Get core eligibility review details."""
    return {
        "review_id": review_id,
        "status": "AI_PENDING",
        "ai_recommendation": "ELIGIBLE",
        "ai_confidence_score": 85,
    }
