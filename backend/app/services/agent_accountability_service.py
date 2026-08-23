"""
Agent Accountability Service - Every agent has ONE job: get more people to 2,000 by 2030.

No silos. No "we did great at our stage" when the next agent fails.
Each agent has a metric directly tied to: "Did this person get hired, stay, and become productive?"

The pipeline is:
Thunder → Qualification → Interview Scheduling → Interview → Offer → Hiring → Onboarding → Productivity

If ANY agent fails, the WHOLE pipeline fails. We measure by:
1. How many candidates did we START with? (Thunder's reach)
2. How many made it through EACH stage?
3. How many actually JOINED and STAYED 90 days?

Accountability:
- Thunder: "I will contact 500 candidates to get 10 to join" (50:1 ratio target)
- Recruitment Agent: "I will screen Thunder's candidates - 40% pass my filter"
- Interview Scheduler: "I will schedule 60% of qualified candidates"
- Hiring Manager Panel: "I will move 50% of interviews to offers"
- Offer Generator: "I will close 80% of offers (candidates accept)"
- Onboarding Agent: "I will keep 95% past day 90"
- Resource Manager: "I will deploy every hire to productive project"

If any link breaks, we escalate to Flash (daily).
If 2+ links broken, escalate to CEO.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.candidate import Candidate
from app.models.offer_letter import OfferLetter
from app.models.employee import Employee
from app.core.logging import logger


class AgentAccountabilityService:
    """Track each agent's accountability to the "2,000 by 2030" goal."""

    @staticmethod
    def get_pipeline_hand_offs(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Show each hand-off in the hiring pipeline and who's responsible.

        Each hand-off is a failure point:
        - If Thunder contacts 500 but Recruitment Agent only qualifies 50 (10% qual rate vs 40% target)
          → Recruitment Agent is the bottleneck
        - If 50 qualified candidates exist but Interview Scheduler only scheduled 10 (20% vs 60% target)
          → Interview Scheduler is the bottleneck

        This service identifies which agent is failing.
        """

        # ===== STAGE 1: THUNDER'S JOB =====
        # "I contact candidates and get them to say 'I'm interested'"
        # Metric: # of candidates Thunder engaged with (has engagement_history)
        thunder_engaged = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.engagement_history.isnot(None)
        ).scalar() or 0

        # ===== STAGE 2: RECRUITMENT AGENT'S JOB =====
        # "I filter Thunder's engaged candidates down to qualified people"
        # Metric: # of candidates who passed qualification screening
        recruitment_qualified = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.status.in_(["QUALIFIED", "SCREENING", "SUBMITTED_TO_JOB", "INTERVIEW", "OFFER", "HIRED"])
        ).scalar() or 0

        # ===== STAGE 3: INTERVIEW SCHEDULER'S JOB =====
        # "I schedule interviews for qualified candidates"
        # Metric: # of interviews scheduled
        interview_scheduled = db.query(func.count(Interview.id)).filter(
            Interview.tenant_id == tenant_id,
            Interview.status != "CANCELLED"
        ).scalar() or 0

        # ===== STAGE 4: HIRING PANEL'S JOB =====
        # "I interview them and give feedback"
        # Metric: # of interviews with feedback (candidate moved toward offer)
        panel_feedback_given = db.query(func.count(Interview.id)).filter(
            Interview.tenant_id == tenant_id,
            Interview.status.in_(["FEEDBACK_GIVEN", "OFFER_EXTENDED"])
        ).scalar() or 0

        # ===== STAGE 5: OFFER GENERATOR'S JOB =====
        # "I create compelling offers that candidates accept"
        # Metric: # of offers sent to candidates
        offers_sent = db.query(func.count(OfferLetter.id)).filter(
            OfferLetter.tenant_id == tenant_id,
            OfferLetter.status != "CANCELLED"
        ).scalar() or 0

        # ===== STAGE 6: OFFER ACCEPTANCE =====
        # "I negotiate and get candidates to say yes"
        # Metric: # of offers accepted (joining_date confirmed)
        offers_accepted = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.joining_date.isnot(None),
            Candidate.status == "OFFER"
        ).scalar() or 0

        # ===== STAGE 7: HR/ONBOARDING'S JOB =====
        # "I create their employee account and start onboarding"
        # Metric: # of employees created
        employees_created = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at >= (datetime.utcnow() - timedelta(days=90))
        ).scalar() or 0

        # ===== STAGE 8: ONBOARDING AGENT'S JOB =====
        # "I complete onboarding and get them productive"
        # Metric: # of employees who completed onboarding
        onboarded = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.onboarding_completed_at.isnot(None),
            Employee.created_at >= (datetime.utcnow() - timedelta(days=90))
        ).scalar() or 0

        # ===== STAGE 9: RESOURCE MANAGER'S JOB =====
        # "I deploy them to a project so they generate revenue"
        # Metric: # of employees allocated to projects
        deployed = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.current_project_id.isnot(None),
            Employee.created_at >= (datetime.utcnow() - timedelta(days=90))
        ).scalar() or 0

        # ===== STAGE 10: EMPLOYEE THEMSELVES =====
        # "I stay past day 90 and perform"
        # Metric: # of employees still active at 90+ days
        retained_90d = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at <= (datetime.utcnow() - timedelta(days=90)),
            Employee.status == "ACTIVE"
        ).scalar() or 0

        # ===== CALCULATE HAND-OFF FAILURES =====
        hand_offs = [
            {
                "from_agent": "Thunder",
                "to_agent": "Recruitment Agent",
                "from_stage": "Engaged",
                "to_stage": "Qualified",
                "started": thunder_engaged,
                "completed": recruitment_qualified,
                "conversion_pct": (recruitment_qualified / max(thunder_engaged, 1)) * 100,
                "target_pct": 40,
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (recruitment_qualified / max(thunder_engaged, 1)) * 100, 40
                ),
                "responsible_agent": "Recruitment Agent",
                "issue": (
                    f"Recruitment Agent only qualified {(recruitment_qualified / max(thunder_engaged, 1)) * 100:.1f}% "
                    f"of Thunder's engaged candidates (target: 40%)"
                    if (recruitment_qualified / max(thunder_engaged, 1)) * 100 < 40 and thunder_engaged > 0
                    else None
                )
            },
            {
                "from_agent": "Recruitment Agent",
                "to_agent": "Interview Scheduler",
                "from_stage": "Qualified",
                "to_stage": "Interview Scheduled",
                "started": recruitment_qualified,
                "completed": interview_scheduled,
                "conversion_pct": (interview_scheduled / max(recruitment_qualified, 1)) * 100,
                "target_pct": 60,
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (interview_scheduled / max(recruitment_qualified, 1)) * 100, 60
                ),
                "responsible_agent": "Interview Scheduler Agent",
                "issue": (
                    f"Interview Scheduler only scheduled {(interview_scheduled / max(recruitment_qualified, 1)) * 100:.1f}% "
                    f"of qualified candidates (target: 60%)"
                    if (interview_scheduled / max(recruitment_qualified, 1)) * 100 < 60 and recruitment_qualified > 0
                    else None
                )
            },
            {
                "from_agent": "Interview Scheduler",
                "to_agent": "Hiring Panel",
                "from_stage": "Interview Scheduled",
                "to_stage": "Interview Feedback Given",
                "started": interview_scheduled,
                "completed": panel_feedback_given,
                "conversion_pct": (panel_feedback_given / max(interview_scheduled, 1)) * 100,
                "target_pct": 100,  # All scheduled interviews should happen
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (panel_feedback_given / max(interview_scheduled, 1)) * 100, 95
                ),
                "responsible_agent": "Hiring Panel",
                "issue": (
                    f"Panel only gave feedback on {(panel_feedback_given / max(interview_scheduled, 1)) * 100:.1f}% "
                    f"of scheduled interviews (target: 95%)"
                    if (panel_feedback_given / max(interview_scheduled, 1)) * 100 < 95 and interview_scheduled > 0
                    else None
                )
            },
            {
                "from_agent": "Hiring Panel",
                "to_agent": "Offer Generator",
                "from_stage": "Interview Feedback",
                "to_stage": "Offer Sent",
                "started": panel_feedback_given,
                "completed": offers_sent,
                "conversion_pct": (offers_sent / max(panel_feedback_given, 1)) * 100,
                "target_pct": 50,  # 50% of interviewed candidates get offers
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (offers_sent / max(panel_feedback_given, 1)) * 100, 50
                ),
                "responsible_agent": "Offer Generator Agent",
                "issue": (
                    f"Offer Generator only sent offers to {(offers_sent / max(panel_feedback_given, 1)) * 100:.1f}% "
                    f"of interviewed candidates (target: 50%)"
                    if (offers_sent / max(panel_feedback_given, 1)) * 100 < 50 and panel_feedback_given > 0
                    else None
                )
            },
            {
                "from_agent": "Offer Generator",
                "to_agent": "Thunder (Offer Negotiation)",
                "from_stage": "Offer Sent",
                "to_stage": "Offer Accepted",
                "started": offers_sent,
                "completed": offers_accepted,
                "conversion_pct": (offers_accepted / max(offers_sent, 1)) * 100,
                "target_pct": 80,  # 80% of offers should be accepted
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (offers_accepted / max(offers_sent, 1)) * 100, 80
                ),
                "responsible_agent": "Thunder (Offer Acceptance)",
                "issue": (
                    f"Only {(offers_accepted / max(offers_sent, 1)) * 100:.1f}% of offers were accepted (target: 80%)"
                    if (offers_accepted / max(offers_sent, 1)) * 100 < 80 and offers_sent > 0
                    else None
                )
            },
            {
                "from_agent": "Thunder",
                "to_agent": "Onboarding Agent",
                "from_stage": "Offer Accepted",
                "to_stage": "Employee Created",
                "started": offers_accepted,
                "completed": employees_created,
                "conversion_pct": (employees_created / max(offers_accepted, 1)) * 100,
                "target_pct": 100,  # All accepted offers → employee accounts
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (employees_created / max(offers_accepted, 1)) * 100, 100
                ),
                "responsible_agent": "HR/Onboarding Agent",
                "issue": (
                    f"Only {(employees_created / max(offers_accepted, 1)) * 100:.1f}% of accepted offers became employee accounts"
                    if (employees_created / max(offers_accepted, 1)) * 100 < 100 and offers_accepted > 0
                    else None
                )
            },
            {
                "from_agent": "HR/Onboarding",
                "to_agent": "Onboarding Agent",
                "from_stage": "Employee Created",
                "to_stage": "Onboarding Completed",
                "started": employees_created,
                "completed": onboarded,
                "conversion_pct": (onboarded / max(employees_created, 1)) * 100,
                "target_pct": 95,  # 95% should complete onboarding
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (onboarded / max(employees_created, 1)) * 100, 95
                ),
                "responsible_agent": "Onboarding Agent",
                "issue": (
                    f"Only {(onboarded / max(employees_created, 1)) * 100:.1f}% of new employees completed onboarding (target: 95%)"
                    if (onboarded / max(employees_created, 1)) * 100 < 95 and employees_created > 0
                    else None
                )
            },
            {
                "from_agent": "Onboarding Agent",
                "to_agent": "Resource Manager",
                "from_stage": "Onboarded",
                "to_stage": "Deployed to Project",
                "started": onboarded,
                "completed": deployed,
                "conversion_pct": (deployed / max(onboarded, 1)) * 100,
                "target_pct": 100,  # All onboarded → deployed
                "status": AgentAccountabilityService._evaluate_hand_off(
                    (deployed / max(onboarded, 1)) * 100, 100
                ),
                "responsible_agent": "Resource Manager",
                "issue": (
                    f"Only {(deployed / max(onboarded, 1)) * 100:.1f}% of onboarded employees deployed to projects"
                    if (deployed / max(onboarded, 1)) * 100 < 100 and onboarded > 0
                    else None
                )
            },
            {
                "from_agent": "Resource Manager",
                "to_agent": "Employee",
                "from_stage": "Deployed",
                "to_stage": "Retained Past 90 Days",
                "started": deployed,
                "completed": retained_90d if retained_90d > 0 else deployed,  # Use deployed if not 90d yet
                "conversion_pct": 100 if deployed == 0 else (retained_90d / deployed * 100),
                "target_pct": 95,  # 95% retention at 90+ days
                "status": "TBD",  # Can't evaluate this yet for recent hires
                "responsible_agent": "Employee + Manager",
                "issue": None  # Retention can't be evaluated for recent hires
            }
        ]

        # Find broken hand-offs
        broken_hand_offs = [h for h in hand_offs if h["issue"] is not None]

        return {
            "hand_offs": hand_offs,
            "broken_count": len(broken_hand_offs),
            "broken_hand_offs": broken_hand_offs,
            "pipeline_summary": {
                "candidates_engaged": thunder_engaged,
                "candidates_qualified": recruitment_qualified,
                "interviews_scheduled": interview_scheduled,
                "interviews_completed": panel_feedback_given,
                "offers_sent": offers_sent,
                "offers_accepted": offers_accepted,
                "employees_created": employees_created,
                "onboarded": onboarded,
                "deployed": deployed,
            },
            "overall_conversion": (onboarded / max(thunder_engaged, 1) * 100) if thunder_engaged > 0 else 0,
            "north_star_metric": f"{deployed} employees deployed in past 90 days (target to 2,000 by 2030)",
        }

    @staticmethod
    def _evaluate_hand_off(actual_pct: float, target_pct: float) -> str:
        """Evaluate if a hand-off is healthy."""
        if actual_pct >= target_pct * 0.95:  # Within 5% of target
            return "HEALTHY"
        elif actual_pct >= target_pct * 0.80:  # Within 20% of target
            return "WARNING"
        else:
            return "CRITICAL"

    @staticmethod
    def get_agent_scorecards(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Individual agent scorecards showing each agent's contribution to "2,000 by 2030".

        Format:
        - Agent name
        - Their job in the pipeline
        - Their current performance metric
        - Their target
        - Health (HEALTHY / WARNING / CRITICAL)
        - What they need to do to improve
        """
        hand_offs = AgentAccountabilityService.get_pipeline_hand_offs(db, tenant_id)

        agents = {
            "Thunder": {
                "job": "Contact candidates and convince them to interview + accept offers",
                "metrics": [
                    f"{hand_offs['pipeline_summary']['candidates_engaged']} candidates contacted",
                    f"{hand_offs['pipeline_summary']['offers_accepted']} offers accepted"
                ],
                "target": "500 candidates contacted to get 10 to join (50:1 ratio)",
                "contribution_to_2000": "Initial reach and engagement - if Thunder doesn't contact, pipeline is empty"
            },
            "Recruitment Agent": {
                "job": "Screen Thunder's contacts and qualify good fits",
                "metrics": [f"{hand_offs['pipeline_summary']['candidates_qualified']} qualified"],
                "target": "40% of Thunder's engaged candidates should be qualified",
                "contribution_to_2000": "Quality gate - bad screening wastes interview time"
            },
            "Interview Scheduler": {
                "job": "Schedule interviews with hiring managers for qualified candidates",
                "metrics": [f"{hand_offs['pipeline_summary']['interviews_scheduled']} scheduled"],
                "target": "60% of qualified candidates should get interview scheduled",
                "contribution_to_2000": "Speed to first interaction - delays kill momentum"
            },
            "Hiring Panel": {
                "job": "Interview and assess candidate quality",
                "metrics": [f"{hand_offs['pipeline_summary']['interviews_completed']} with feedback"],
                "target": "95% of scheduled interviews should provide feedback",
                "contribution_to_2000": "Quality assessment - decides who moves to offers"
            },
            "Offer Generator": {
                "job": "Create compelling offers that candidates accept",
                "metrics": [f"{hand_offs['pipeline_summary']['offers_sent']} sent"],
                "target": "50% of interviews should result in offers",
                "contribution_to_2000": "Offer quality - bad offers = rejections"
            },
            "Thunder (Offer Acceptance)": {
                "job": "Negotiate and close offers - get YES",
                "metrics": [f"{hand_offs['pipeline_summary']['offers_accepted']} accepted"],
                "target": "80% of offers should be accepted",
                "contribution_to_2000": "Final conversion - if they say no, whole pipeline failed"
            },
            "HR/Onboarding": {
                "job": "Create employee account and begin onboarding",
                "metrics": [f"{hand_offs['pipeline_summary']['employees_created']} created"],
                "target": "100% of accepted offers → employee accounts",
                "contribution_to_2000": "Onboarding kickoff - admin but critical"
            },
            "Onboarding Agent": {
                "job": "Complete 30/60/90 day onboarding workflow",
                "metrics": [f"{hand_offs['pipeline_summary']['onboarded']} completed"],
                "target": "95% of new hires should complete onboarding",
                "contribution_to_2000": "Success in first 90 days - completion drives retention"
            },
            "Resource Manager": {
                "job": "Allocate onboarded employees to projects",
                "metrics": [f"{hand_offs['pipeline_summary']['deployed']} deployed"],
                "target": "100% of onboarded employees → productive projects",
                "contribution_to_2000": "Deployment = revenue generation starts"
            }
        }

        return {
            "agents": agents,
            "hand_offs": hand_offs,
            "north_star": f"Target: {hand_offs['pipeline_summary']['deployed']} employees deployed per 90 days to reach 2,000 by 2030"
        }
