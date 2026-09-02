"""
import logging
Recruitment Funnel Dashboard - Real-time visibility into Phase 1 agent effectiveness.

Shows the complete candidate journey through our autonomous hiring pipeline:
Thunder (contact) → Recruitment Agent (qualify) → Supervisor (manage lifecycle)
→ HTD Pipeline (develop) → Offer → Hire → Onboard

Metrics tracked:
- How many candidates at each stage?
- What % are converting to next stage?
- Where are bottlenecks (people getting stuck)?
- Are we on pace to 2,000 employees by 2030?

This is the ONLY dashboard that answers: "Are Phase 1 agents working?"
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.candidate import Candidate
from app.models.offer_letter import OfferLetter
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit

logger = logging.getLogger(__name__)

class RecruitmentFunnelDashboard:
    """Real-time recruitment funnel showing all 5 pillars."""

    @staticmethod
    def get_full_funnel(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Get complete recruitment funnel:

        RECRUITMENT (Phase 1):
        ├─ Contacted (Thunder did its job - candidate has engagement)
        ├─ Qualified (Recruitment Agent screened them)
        ├─ Interview Scheduled (Supervisor + Interview Reminder coordinating)
        ├─ Interviewed (Complete)
        ├─ Offer Extended (Offer Generator + Recruiter approved)
        ├─ Offer Accepted (Candidate said yes)
        ├─ Hired (Employee account created)
        └─ Onboarded (Onboarding Agent completed workflow)

        SALES (pipeline health):
        ├─ Total pipeline value
        ├─ Deals at each stage
        └─ Probability-weighted forecast

        DELIVERY:
        ├─ Projects with full teams
        ├─ Utilization rate
        └─ Quality metrics (TBD)

        RESOURCE MANAGEMENT:
        ├─ CORE certified
        ├─ In development (HTD)
        ├─ Bench availability
        └─ Utilization by BU

        EMPLOYEE HAPPINESS:
        ├─ New hire satisfaction (pulse survey)
        ├─ Retention rate (first 90 days)
        ├─ Onboarding completion
        └─ Mental health indicators
        """

        # ===== RECRUITMENT FUNNEL =====
        recruitment = RecruitmentFunnelDashboard._get_recruitment_funnel(db, tenant_id)

        # ===== SALES PIPELINE =====
        # TODO: Implement when Opportunity Tracker is fully wired
        sales = {
            "total_pipeline_usd": 0,
            "deals": [],
            "probability_weighted": 0,
            "status": "NOT_YET_IMPLEMENTED"
        }

        # ===== DELIVERY =====
        # TODO: Implement when project/delivery metrics are tracked
        delivery = {
            "active_projects": 0,
            "fully_staffed": 0,
            "utilization_pct": 0,
            "quality_score": 0,
            "status": "NOT_YET_IMPLEMENTED"
        }

        # ===== RESOURCE MANAGEMENT =====
        resources = RecruitmentFunnelDashboard._get_resource_health(db, tenant_id)

        # ===== EMPLOYEE HAPPINESS =====
        happiness = RecruitmentFunnelDashboard._get_employee_happiness(db, tenant_id)

        # ===== 2030 PROGRESS =====
        progress_2030 = RecruitmentFunnelDashboard._calculate_2030_trajectory(
            db, tenant_id, recruitment, resources
        )

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "recruitment": recruitment,
            "sales": sales,
            "delivery": delivery,
            "resources": resources,
            "employee_happiness": happiness,
            "progress_2030": progress_2030,
            "health_summary": RecruitmentFunnelDashboard._get_health_summary(
                recruitment, resources, happiness
            )
        }

    @staticmethod
    def _get_recruitment_funnel(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get the recruitment funnel with conversion metrics."""

        # Stage 1: CONTACTED (Thunder did its job)
        # Definition: Candidate has engagement history (email/WhatsApp/call) OR in Thunder's queue
        contacted_count = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.engagement_history.isnot(None),  # Has been contacted
        ).scalar() or 0

        # Stage 2: QUALIFIED (Recruitment Agent screened)
        # Definition: Candidate status is QUALIFIED or beyond
        qualified_count = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.status.in_(["QUALIFIED", "SCREENING", "SUBMITTED_TO_JOB", "INTERVIEW", "OFFER", "HIRED"])
        ).scalar() or 0

        # Stage 3: INTERVIEW SCHEDULED
        # Definition: Interview exists for this candidate
        interview_scheduled = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.candidateID.in_(
                db.query(Interview.candidate_id).filter(
                    Interview.tenant_id == tenant_id,
                    Interview.status.in_(["SCHEDULED", "COMPLETED", "FEEDBACK_GIVEN"])
                )
            )
        ).scalar() or 0

        # Stage 4: INTERVIEWED (Panel feedback complete)
        interviewed_count = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.candidateID.in_(
                db.query(Interview.candidate_id).filter(
                    Interview.tenant_id == tenant_id,
                    Interview.status.in_(["FEEDBACK_GIVEN", "OFFER_EXTENDED"])
                )
            )
        ).scalar() or 0

        # Stage 5: OFFER EXTENDED
        offer_extended = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.candidateID.in_(
                db.query(OfferLetter.candidate_id).filter(
                    OfferLetter.tenant_id == tenant_id,
                    OfferLetter.status.in_(["SENT", "ACCEPTED", "STARTED"])
                )
            )
        ).scalar() or 0

        # Stage 6: OFFER ACCEPTED
        offer_accepted = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.candidateID.in_(
                db.query(OfferLetter.candidate_id).filter(
                    OfferLetter.tenant_id == tenant_id,
                    OfferLetter.status.in_(["ACCEPTED", "STARTED"])
                )
            )
        ).scalar() or 0

        # Stage 7: HIRED (Employee account created)
        hired_count = db.query(func.count(Candidate.candidateID)).filter(
            Candidate.tenant_id == tenant_id,
            Candidate.status == "HIRED"
        ).scalar() or 0

        # Stage 8: ONBOARDED (Onboarding complete)
        onboarded_count = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.onboarding_completed_at.isnot(None)
        ).scalar() or 0

        # Calculate conversions
        contacted_to_qualified = (qualified_count / contacted_count * 100) if contacted_count > 0 else 0
        qualified_to_interview = (interview_scheduled / qualified_count * 100) if qualified_count > 0 else 0
        interview_to_offer = (offer_extended / interviewed_count * 100) if interviewed_count > 0 else 0
        offer_to_hire = (hired_count / offer_accepted * 100) if offer_accepted > 0 else 0
        hire_to_onboard = (onboarded_count / hired_count * 100) if hired_count > 0 else 0

        # Overall funnel efficiency
        overall_efficiency = (onboarded_count / contacted_count * 100) if contacted_count > 0 else 0

        # Blockers (where are people stuck?)
        blockers = []
        if contacted_to_qualified < 30:  # Less than 30% of contacted → qualified
            blockers.append({
                "severity": "HIGH",
                "issue": "Low qualification rate",
                "metric": f"{contacted_to_qualified:.1f}%",
                "target": "40%+",
                "owner": "Recruitment Agent",
                "action": "Review screening criteria - may be too strict or Thunder is sending poor fits"
            })

        if qualified_to_interview < 50:  # Less than 50% qualified → interviewed
            blockers.append({
                "severity": "HIGH",
                "issue": "Interview scheduling bottleneck",
                "metric": f"{qualified_to_interview:.1f}%",
                "target": "60%+",
                "owner": "Interview Reminder Agent + Supervisor",
                "action": "Check interview availability + candidate responsiveness"
            })

        if interview_to_offer < 40:  # Less than 40% interviewed → offer
            blockers.append({
                "severity": "MEDIUM",
                "issue": "Panel feedback quality",
                "metric": f"{interview_to_offer:.1f}%",
                "target": "50%+",
                "owner": "Hiring Panel + Offer Generator",
                "action": "Review interview scores - may need panel calibration"
            })

        if offer_to_hire < 70:  # Less than 70% offer → hire
            blockers.append({
                "severity": "HIGH",
                "issue": "Offer acceptance rate low",
                "metric": f"{offer_to_hire:.1f}%",
                "target": "85%+",
                "owner": "Offer Generator + Thunder",
                "action": "Check offer competitiveness + candidate engagement"
            })

        return {
            "stages": [
                {
                    "stage": "Contacted",
                    "count": contacted_count,
                    "agent": "Thunder",
                    "description": "Candidate has been contacted by Thunder via email/WhatsApp"
                },
                {
                    "stage": "Qualified",
                    "count": qualified_count,
                    "conversion_from_prev": round(contacted_to_qualified, 1),
                    "agent": "Recruitment Agent",
                    "description": "Passed screening criteria, qualified for interview"
                },
                {
                    "stage": "Interview Scheduled",
                    "count": interview_scheduled,
                    "conversion_from_prev": round(qualified_to_interview, 1),
                    "agent": "Supervisor + Interview Reminder",
                    "description": "Interview scheduled with hiring panel"
                },
                {
                    "stage": "Interviewed",
                    "count": interviewed_count,
                    "conversion_from_prev": 100,  # All scheduled = interviewed
                    "agent": "Hiring Panel",
                    "description": "Interview complete, feedback gathered"
                },
                {
                    "stage": "Offer Extended",
                    "count": offer_extended,
                    "conversion_from_prev": round(interview_to_offer, 1),
                    "agent": "Offer Generator",
                    "description": "Offer letter generated and sent"
                },
                {
                    "stage": "Offer Accepted",
                    "count": offer_accepted,
                    "conversion_from_prev": round(offer_to_hire, 1),
                    "agent": "Thunder + Recruiter",
                    "description": "Candidate accepted offer, joining date confirmed"
                },
                {
                    "stage": "Hired",
                    "count": hired_count,
                    "conversion_from_prev": 100,  # All accepted → hired immediately
                    "agent": "Employee Management",
                    "description": "Employee account created in WROS"
                },
                {
                    "stage": "Onboarded",
                    "count": onboarded_count,
                    "conversion_from_prev": round(hire_to_onboard, 1),
                    "agent": "Onboarding Agent",
                    "description": "Onboarding workflow complete, employee productive"
                }
            ],
            "overall_efficiency": round(overall_efficiency, 1),
            "blockers": blockers,
            "health": "HEALTHY" if len(blockers) == 0 else "WARNING" if len(blockers) <= 2 else "CRITICAL",
            "monthly_hires": RecruitmentFunnelDashboard._get_monthly_hires(db, tenant_id),
            "required_pace": RecruitmentFunnelDashboard._calculate_required_pace(db, tenant_id)
        }

    @staticmethod
    def _get_resource_health(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get resource management metrics (utilization, CORE certification, HTD progress)."""

        # Total active employees
        total_employees = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        # CORE certified employees
        core_certified = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "ACTIVE",
            Employee.is_core_certified == True
        ).scalar() or 0

        # In development (HTD pipeline)
        in_development = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "TRAINING"
        ).scalar() or 0

        # On bench (not allocated to project)
        on_bench = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "ACTIVE",
            Employee.current_project_id.is_(None)
        ).scalar() or 0

        # Utilization calculation (employees on projects / total active)
        allocated = total_employees - on_bench
        utilization_pct = (allocated / total_employees * 100) if total_employees > 0 else 0

        # CORE % (should be 60%+)
        core_pct = (core_certified / total_employees * 100) if total_employees > 0 else 0

        # By business unit
        bu_breakdown = []
        business_units = db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == tenant_id
        ).all()

        for bu in business_units:
            bu_total = db.query(func.count(Employee.id)).filter(
                Employee.tenant_id == tenant_id,
                Employee.business_unit_id == bu.id,
                Employee.status == "ACTIVE"
            ).scalar() or 0

            bu_core = db.query(func.count(Employee.id)).filter(
                Employee.tenant_id == tenant_id,
                Employee.business_unit_id == bu.id,
                Employee.status == "ACTIVE",
                Employee.is_core_certified == True
            ).scalar() or 0

            bu_breakdown.append({
                "bu_name": bu.name,
                "total": bu_total,
                "core_certified": bu_core,
                "core_pct": (bu_core / bu_total * 100) if bu_total > 0 else 0,
                "in_development": db.query(func.count(Employee.id)).filter(
                    Employee.business_unit_id == bu.id,
                    Employee.status == "TRAINING"
                ).scalar() or 0
            })

        return {
            "total_active_employees": total_employees,
            "core_certified": core_certified,
            "core_pct": round(core_pct, 1),
            "core_target": 60,  # 60% CORE by 2030
            "in_development": in_development,
            "on_bench": on_bench,
            "utilization_pct": round(utilization_pct, 1),
            "utilization_target": 75,  # Target utilization
            "health": "HEALTHY" if utilization_pct >= 75 and core_pct >= 50 else "WARNING",
            "by_business_unit": bu_breakdown
        }

    @staticmethod
    def _get_employee_happiness(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get employee happiness and retention metrics."""

        # New hires (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_hires = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at >= thirty_days_ago
        ).scalar() or 0

        # Retention rate (employees still active who were hired 90+ days ago)
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        hired_90_days_ago = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at <= ninety_days_ago
        ).scalar() or 0

        still_active = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at <= ninety_days_ago,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        retention_pct = (still_active / hired_90_days_ago * 100) if hired_90_days_ago > 0 else 0

        # Onboarding completion (from Onboarding Agent)
        onboarded_recently = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.created_at >= thirty_days_ago,
            Employee.onboarding_completed_at.isnot(None)
        ).scalar() or 0

        # Note: Pulse survey, mental health indicators TBD (need integration with HR Agent)

        return {
            "new_hires_30d": new_hires,
            "retention_90d_pct": round(retention_pct, 1),
            "retention_target": 95,  # Target: 95% retention
            "onboarding_completion": round((onboarded_recently / max(new_hires, 1) * 100), 1),
            "health": "HEALTHY" if retention_pct >= 95 else "WARNING",
            "notes": "Pulse surveys and mental health indicators require HR Agent integration (not yet implemented)"
        }

    @staticmethod
    def _calculate_2030_trajectory(
        db: Session,
        tenant_id: str,
        recruitment: Dict,
        resources: Dict
    ) -> Dict[str, Any]:
        """Calculate if we're on pace to reach 2,000 employees by 2030."""

        current_headcount = resources["total_active_employees"]
        days_to_2030 = (datetime(2030, 12, 31) - datetime.utcnow()).days
        years_to_2030 = days_to_2030 / 365

        # Current monthly hire rate (from recruitment funnel)
        monthly_hires = recruitment.get("monthly_hires", {}).get("avg_monthly", 0)

        # Projected headcount at current rate
        months_to_2030 = days_to_2030 / 30
        projected_at_current_rate = current_headcount + (monthly_hires * months_to_2030)

        # Required monthly hire rate to hit 2,000
        required_employees = 2000 - current_headcount
        required_monthly_rate = required_employees / months_to_2030 if months_to_2030 > 0 else 0

        # On track?
        on_track = monthly_hires >= required_monthly_rate * 0.95  # Within 5% of target

        return {
            "target_employees_2030": 2000,
            "current_headcount": current_headcount,
            "gap": 2000 - current_headcount,
            "years_remaining": round(years_to_2030, 1),
            "current_monthly_hire_rate": round(monthly_hires, 1),
            "required_monthly_hire_rate": round(required_monthly_rate, 1),
            "projected_at_current_rate": int(projected_at_current_rate),
            "on_track": on_track,
            "pace_rating": (monthly_hires / required_monthly_rate * 100) if required_monthly_rate > 0 else 0,
            "health": "ON_TRACK" if on_track else "BEHIND"
        }

    @staticmethod
    def _get_health_summary(recruitment: Dict, resources: Dict, happiness: Dict) -> Dict[str, Any]:
        """Summarize overall system health across all 5 pillars."""

        issues = []

        # Recruitment issues
        if recruitment.get("health") == "CRITICAL":
            issues.append("Recruitment funnel has critical blockers")

        # Resource issues
        if resources.get("health") != "HEALTHY":
            issues.append(f"Resource utilization below target ({resources.get('utilization_pct')}% vs 75%)")
            if resources.get("core_pct", 0) < 50:
                issues.append("CORE certification below target - HTD pipeline needs acceleration")

        # Happiness issues
        if happiness.get("health") != "HEALTHY":
            issues.append(f"Retention rate {happiness.get('retention_90d_pct')}% below target (95%)")

        # Overall health
        overall = "HEALTHY"
        if len(issues) >= 2:
            overall = "CRITICAL"
        elif len(issues) == 1:
            overall = "WARNING"

        return {
            "overall_health": overall,
            "issues_identified": len(issues),
            "critical_issues": issues,
            "next_action": RecruitmentFunnelDashboard._get_recommended_action(
                recruitment, resources, happiness
            )
        }

    @staticmethod
    def _get_recommended_action(recruitment: Dict, resources: Dict, happiness: Dict) -> str:
        """Get the most important action to take right now."""

        # Recruitment bottleneck?
        recruitment_blockers = recruitment.get("blockers", [])
        if recruitment_blockers:
            top_blocker = recruitment_blockers[0]
            return f"PRIORITY: Fix recruitment bottleneck: {top_blocker['issue']} (Owner: {top_blocker['owner']})"

        # Resource utilization?
        if resources.get("utilization_pct", 0) < 70:
            return f"PRIORITY: Improve resource utilization (currently {resources.get('utilization_pct')}%, target 75%)"

        # Retention?
        if happiness.get("retention_90d_pct", 0) < 90:
            return f"PRIORITY: Focus on employee retention (currently {happiness.get('retention_90d_pct')}%, target 95%)"

        # On track to 2030?
        if not recruitment.get("progress_2030", {}).get("on_track"):
            return "Acceleration needed: Hiring pace below 2030 target"

        return "All systems healthy - maintain current execution"

    @staticmethod
    def _get_monthly_hires(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Get monthly hiring metrics for last 6 months."""

        monthly_data = []
        total_hires = 0

        for i in range(6, 0, -1):
            month_start = datetime.utcnow() - timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)

            month_hires = db.query(func.count(Employee.id)).filter(
                Employee.tenant_id == tenant_id,
                Employee.created_at >= month_start,
                Employee.created_at < month_end
            ).scalar() or 0

            monthly_data.append({
                "month": month_start.strftime("%B %Y"),
                "hires": month_hires
            })

            total_hires += month_hires

        avg_monthly = total_hires / 6 if total_hires > 0 else 0

        return {
            "monthly_breakdown": monthly_data,
            "total_6_month": total_hires,
            "avg_monthly": round(avg_monthly, 1)
        }

    @staticmethod
    def _calculate_required_pace(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Calculate required hiring pace to hit 2030 target."""

        current_headcount = db.query(func.count(Employee.id)).filter(
            Employee.tenant_id == tenant_id,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        days_to_2030 = (datetime(2030, 12, 31) - datetime.utcnow()).days
        months_to_2030 = days_to_2030 / 30

        required_employees = 2000 - current_headcount
        required_monthly = required_employees / months_to_2030 if months_to_2030 > 0 else 0
        required_annual = required_monthly * 12

        return {
            "required_monthly": round(required_monthly, 1),
            "required_annually": round(required_annual, 0),
            "target_year_2030": 2000,
            "current_headcount": current_headcount
        }
