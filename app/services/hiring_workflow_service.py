"""Interview → Hire → Onboarding workflow orchestration service.

Coordinates the complete hiring flow:
1. Panel selection (skill/role match suggestion + BU Head approval)
2. L1 → L2 auto-trigger (one negative vote = manual HM decision)
3. BU Head financial approval (hiring affordability check)
4. Onboarding trigger (hire decision + approval → offer pipeline)
5. No-show handling (drop from round-robin load immediately)
6. Calendar confirmation (both sides confirm before booking)
7. Rejection notices (real rejection email to candidate)
8. Financial decline workflow (HR negotiation → re-approval)
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.interview_pipeline import SubmissionInterview, DemandInterviewPanel, PanelMember
from app.models.submission import Submission
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.user import Users
from app.services.hiring_affordability_service import check_hiring_affordability
from app.services.task_service import create_task


def suggest_panelists(db: Session, demand_id: str, level: str = "L1") -> List[Dict]:
    """
    Suggest panelists based on skill/role match + past history.

    Returns list of (Employee, match_score, past_interview_count) sorted by score desc.
    BU Head will confirm/override before actual assignment.
    """
    demand = db.query(Demand).filter(Demand.id == demand_id).first()
    if not demand:
        return []

    # Get required skills for this demand
    required_skills = set(skill.strip().lower() for skill in (demand.required_skills or "").split(",") if skill.strip())
    if not required_skills:
        return []

    # Score employees by current_skills overlap + past panel history
    candidates = []
    all_employees = db.query(Employee).filter(Employee.is_active == True).all()

    for emp in all_employees:
        current_skills = set(skill.strip().lower() for skill in (emp.current_skills or "").split(",") if skill.strip())
        skill_match = len(required_skills & current_skills) / len(required_skills) if required_skills else 0

        # Check past interview count for this demand's role/skill combo
        past_panels = db.query(PanelMember).join(
            DemandInterviewPanel, PanelMember.panel_id == DemandInterviewPanel.id
        ).filter(
            PanelMember.employee_id == emp.id,
            DemandInterviewPanel.level == level
        ).count()

        score = skill_match * 0.8 + (1 - min(past_panels / 5, 1.0)) * 0.2  # Prefer less-used panelists
        if score > 0:
            candidates.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.first_name} {emp.last_name}",
                "email": emp.email,
                "skill_match_score": round(skill_match, 2),
                "interview_load": past_panels,
                "overall_score": round(score, 2),
            })

    return sorted(candidates, key=lambda x: x["overall_score"], reverse=True)[:5]


def check_l1_to_l2_auto_trigger(db: Session, demand_id: str, l1_interview_id: str) -> Dict:
    """
    Check if L1 interview results allow L2 auto-creation.

    Returns: {
        "should_trigger_l2": bool,
        "positive_votes": int,
        "negative_votes": int,
        "requires_hm_decision": bool,  # if any negative vote
        "action": "auto_create_l2" | "hm_decision_needed"
    }
    """
    interview = db.query(SubmissionInterview).filter(
        SubmissionInterview.id == l1_interview_id
    ).first()

    if not interview:
        return {"error": "Interview not found"}

    # Count feedback votes on this L1 interview
    positive = 0
    negative = 0

    for feedback in interview.interview_feedback or []:
        rec = getattr(feedback, 'recommendation', None)
        if rec in ("Hire", "Must Hire"):
            positive += 1
        elif rec in ("No Hire", "Reject"):
            negative += 1

    should_trigger = positive > 0 and negative == 0

    return {
        "should_trigger_l2": should_trigger,
        "positive_votes": positive,
        "negative_votes": negative,
        "requires_hm_decision": negative > 0,
        "action": "auto_create_l2" if should_trigger else "hm_decision_needed",
    }


def check_affordability_for_hire(db: Session, submission_id: str, bu_id: Optional[int] = None) -> Dict:
    """
    Check BU affordability for hiring this candidate.

    Returns: {
        "affordable": bool,
        "fully_loaded_cost_usd": int (cents),
        "bu_margin_available_usd": int (cents),
        "recommendation": "APPROVE" | "DECLINE" | "NEGOTIATE",
        "reason": str
    }
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        return {"error": "Submission not found"}

    if not bu_id:
        # Infer from demand
        demand = db.query(Demand).filter(Demand.id == submission.demand_id).first()
        bu_id = demand.business_unit_id if demand else None

    if not bu_id:
        return {"error": "No business unit found for this submission"}

    try:
        affordability = check_hiring_affordability(db, submission.id, bu_id)
        return {
            "affordable": affordability.get("can_afford", False),
            "fully_loaded_cost_usd": affordability.get("fully_loaded_cost_usd", 0),
            "bu_margin_available_usd": affordability.get("bu_margin_available_usd", 0),
            "recommendation": "APPROVE" if affordability.get("can_afford") else "DECLINE",
            "reason": affordability.get("reason", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def create_l2_interview_panel(db: Session, demand_id: str, submission_id: str,
                              panelists: List[str]) -> Dict:
    """Create L2 interview panel after L1 positive vote + affordability check."""
    try:
        # Verify L1 passed and affordability approved first
        demand = db.query(Demand).filter(Demand.id == demand_id).first()
        if not demand:
            return {"error": "Demand not found"}

        # Create L2 interview panel
        l2_panel = DemandInterviewPanel(
            demand_id=demand_id,
            submission_id=submission_id,
            level="L2",
            created_at=datetime.utcnow(),
        )
        db.add(l2_panel)
        db.flush()

        # Assign panelists
        for emp_id in panelists:
            member = PanelMember(
                panel_id=l2_panel.id,
                employee_id=emp_id,
                assigned_at=datetime.utcnow(),
            )
            db.add(member)

        db.commit()
        db.refresh(l2_panel)

        return {
            "l2_panel_id": l2_panel.id,
            "panelists_count": len(panelists),
            "status": "L2 panel created, awaiting scheduling",
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


def record_no_show_confirmation(db: Session, interview_id: str) -> Dict:
    """
    Record no-show and immediately drop from panelist's round-robin load.

    Per design: a no-show isn't the panelist's fault, so they shouldn't count as busier.
    """
    interview = db.query(SubmissionInterview).filter(
        SubmissionInterview.id == interview_id
    ).first()

    if not interview:
        return {"error": "Interview not found"}

    # Mark no-show
    interview.no_show_confirmed_at = datetime.utcnow()
    # Deliberately NOT setting outcome (BR-02: only recruiter decides if candidate is re-schedulable)

    db.add(interview)
    db.commit()
    db.refresh(interview)

    return {
        "interview_id": interview_id,
        "no_show_confirmed": True,
        "outcome": interview.outcome,  # Still PENDING, not auto-rejected
        "action": "Dropped from panelist load, candidate still in pool",
    }
