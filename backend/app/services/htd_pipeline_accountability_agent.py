"""
import logging
HTD Pipeline Accountability Agent

Tracks SPECIALTY→CORE conversion pipeline for each partner.
NOT a tracker. A COACH that shows partners exactly what they need to do to hit CORE targets.

BlitzenX Model:
- Hire offshore into SPECIALTY (bench-funded, cost center)
- Develop through 4 HTD phases over ~90 days
- Pass all gates → COMPLETED → move to CORE (revenue-generating, profit center)
- If development pipeline too slow → HTD (hire external CORE directly)

Partner Focus: "Here's your CORE conversion forecast. Here's where people are stuck. Here's what you need to do."
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.core.agent_logging import log_agent_execution
from app.models.employee import Employee
from app.models.htd_phase_gate import HTDPhaseGate, HTD_GATE_PHASES
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.services.performance_store_service import write_performance_event

logger = logging.getLogger(__name__)

class HTDPipelineAccountabilityAgent:
    """
    Tracks SPECIALTY→CORE conversion by partner/BU, projects CORE capacity.

    ABSOLUTE RULE: Each BU solves its own HTD problem independently.
    No cross-BU resource borrowing, ever.
    """

    HTD_PHASES = HTD_GATE_PHASES  # INDUCTION → SHADOW_DELIVERY → CONTROLLED_OWNERSHIP → CORE_ELIGIBILITY_REVIEW

    @staticmethod
    def validate_no_cross_bu_borrowing(recommendation: Dict[str, Any]) -> bool:
        """
        Validate that a recommendation doesn't suggest cross-BU resource borrowing.

        Forbidden patterns:
        - "borrow", "pull from", "use another", "cross-bu", "other bu", "share with"

        Returns: True if recommendation is valid (autonomous solution), False otherwise.
        """
        forbidden_phrases = [
            "borrow", "pull from", "use another", "cross-bu", "other bu", "share with",
            "get from", "take from", "reallocate from another",
        ]

        rec_str = str(recommendation).lower()
        for phrase in forbidden_phrases:
            if phrase in rec_str:
                return False

        return True

    @staticmethod
    @log_agent_execution("HTD Pipeline Agent", "track_bu_pipeline")
    async def track_bu_pipeline(
        tenant_id: str,
        bu_id: int,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Deep dive into a BU's (partner's) SPECIALTY→CORE pipeline.

        Shows:
        - Current CORE headcount (revenue-generating)
        - SPECIALTY in development (cost center, developing to CORE)
        - Pipeline by HTD phase (where are they stuck?)
        - Conversion forecast (when will they become CORE?)
        - HTD trigger (if conversion too slow, recommend external hire)
        """
        try:
            bu = db.query(BusinessUnit).filter(
                BusinessUnit.id == bu_id,
                BusinessUnit.tenant_id == tenant_id
            ).first()

            if not bu:
                raise ValueError(f"BU {bu_id} not found for tenant {tenant_id}")

            # 1. Get all employees in this BU
            all_employees = db.query(Employee).filter(
                Employee.tenant_id == tenant_id,
                Employee.bu_id == bu_id,
                Employee.status != "EXITED"
            ).all()

            # 2. Split by delivery engine + HTD status
            core_certified = [e for e in all_employees if e.delivery_engine == "CORE"]
            specialty_in_htd = [e for e in all_employees if e.delivery_engine == "SPECIALITY" and e.htd_track]
            specialty_no_htd = [e for e in all_employees if e.delivery_engine == "SPECIALITY" and not e.htd_track]

            # 3. Analyze HTD pipeline by phase
            pipeline_by_phase = {phase: [] for phase in HTDPipelineAccountabilityAgent.HTD_PHASES + ("COMPLETED", "EXITED")}

            for emp in specialty_in_htd:
                phase = emp.htd_phase or "INDUCTION"
                if phase in pipeline_by_phase:
                    pipeline_by_phase[phase].append({
                        "employee_id": emp.id,
                        "name": f"{emp.first_name} {emp.last_name}",
                        "htd_start_date": emp.htd_start_date.isoformat() if emp.htd_start_date else None,
                        "days_in_current_phase": (datetime.now().date() - emp.htd_start_date).days if emp.htd_start_date else None,
                    })

            # 4. Get latest gate decisions for each phase
            gate_readiness = {}
            for phase in HTDPipelineAccountabilityAgent.HTD_PHASES:
                latest_gates = db.query(HTDPhaseGate).filter(
                    HTDPhaseGate.phase == phase,
                    HTDPhaseGate.employee_id.in_([e.id for e in specialty_in_htd])
                ).order_by(HTDPhaseGate.decided_at.desc()).all()

                pass_count = len([g for g in latest_gates if g.gate_decision == "PASS"])
                fail_count = len([g for g in latest_gates if g.gate_decision == "FAIL"])
                extend_count = len([g for g in latest_gates if g.gate_decision == "EXTEND"])

                gate_readiness[phase] = {
                    "pass": pass_count,
                    "fail": fail_count,
                    "extend": extend_count,
                    "total_evaluated": pass_count + fail_count + extend_count,
                }

            # 5. Calculate conversion forecast (if no more failures)
            core_forecast = len(core_certified)
            completed_in_pipeline = len(pipeline_by_phase.get("COMPLETED", []))
            core_forecast += completed_in_pipeline

            # Optimistic forecast: assume all passes at next gate move forward
            for phase in HTDPipelineAccountabilityAgent.HTD_PHASES[:-1]:  # not CORE_ELIGIBILITY_REVIEW
                if gate_readiness[phase]["pass"] > 0:
                    core_forecast += gate_readiness[phase]["pass"]

            # 6. Conversion velocity
            days_since_first_htd_start = None
            earliest_htd = min(
                [e.htd_start_date for e in specialty_in_htd if e.htd_start_date],
                default=None
            )
            if earliest_htd:
                days_since_first_htd_start = (datetime.now().date() - earliest_htd).days

            # 7. Build recommendations (MUST BE BU AUTONOMOUS)
            recommendations = []

            # Stuck at any phase?
            for phase, readiness in gate_readiness.items():
                if readiness["fail"] > 0:
                    rec = {
                        "priority": "CRITICAL",
                        "action": f"Address {readiness['fail']} failure(s) at {phase} gate",
                        "reason": f"{readiness['fail']} people didn't pass. Need coaching/support immediately.",
                        "bu_autonomous": True,
                    }
                    if not HTDPipelineAccountabilityAgent.validate_no_cross_bu_borrowing(rec):
                        raise ValueError(f"INVALID RECOMMENDATION: Cross-BU borrowing in {bu.name} recommendation")
                    recommendations.append(rec)

                if readiness["extend"] > 0:
                    rec = {
                        "priority": "HIGH",
                        "action": f"Monitor {readiness['extend']} extended at {phase}",
                        "reason": f"{readiness['extend']} people got extension. If they fail next eval, must EXIT.",
                        "bu_autonomous": True,
                    }
                    if not HTDPipelineAccountabilityAgent.validate_no_cross_bu_borrowing(rec):
                        raise ValueError(f"INVALID RECOMMENDATION: Cross-BU borrowing in {bu.name} recommendation")
                    recommendations.append(rec)

            # HTD trigger: if conversion forecast < target
            target_core = len(all_employees) * 0.6  # Default: 60% should be CORE
            if core_forecast < target_core:
                gap = int(target_core - core_forecast)
                rec = {
                    "priority": "STRATEGIC",
                    "action": f"HTD: Hire {gap} external CORE to bridge gap ({bu.name} owns this)",
                    "reason": f"Development forecast: {core_forecast} CORE (vs {target_core} needed). "
                              f"Internal pipeline slow. {bu.name} must source external hire.",
                    "timeline": "Can hire external CORE in weeks, vs 90 days to develop internal",
                    "bu_autonomous": True,
                    "cross_bu_forbidden": f"NO: {bu.name} solves this independently. Do not suggest borrowing from other BUs.",
                }
                if not HTDPipelineAccountabilityAgent.validate_no_cross_bu_borrowing(rec):
                    raise ValueError(f"INVALID RECOMMENDATION: Cross-BU borrowing in {bu.name} recommendation")
                recommendations.append(rec)

            result = {
                "status": "success",
                "bu": bu.name,
                "bu_id": bu.id,
                "date": datetime.now().date().isoformat(),

                # PEOPLE SUMMARY
                "headcount": {
                    "total": len(all_employees),
                    "core_certified": len(core_certified),
                    "specialty_in_development": len(specialty_in_htd),
                    "specialty_no_htd": len(specialty_no_htd),
                },

                # CORE CERTIFICATION RATIO
                "core_ratio": {
                    "current_pct": round(len(core_certified) / len(all_employees) * 100, 1) if all_employees else 0,
                    "target_pct": 60,
                    "gap": max(0, int((len(all_employees) * 0.6) - len(core_certified))),
                },

                # HTD PIPELINE DETAIL
                "htd_pipeline": {
                    "induction": pipeline_by_phase["INDUCTION"],
                    "shadow_delivery": pipeline_by_phase["SHADOW_DELIVERY"],
                    "controlled_ownership": pipeline_by_phase["CONTROLLED_OWNERSHIP"],
                    "core_eligibility_review": pipeline_by_phase["CORE_ELIGIBILITY_REVIEW"],
                    "completed": pipeline_by_phase["COMPLETED"],
                    "exited": pipeline_by_phase["EXITED"],
                },

                # GATE READINESS (WHO'S READY TO PASS?)
                "gate_readiness": gate_readiness,

                # CONVERSION FORECAST
                "core_forecast": {
                    "current_core": len(core_certified),
                    "in_pipeline_completed": completed_in_pipeline,
                    "optimistic_forecast_if_all_pass": core_forecast,
                    "forecast_pct_of_headcount": round(core_forecast / len(all_employees) * 100, 1) if all_employees else 0,
                },

                # CONVERSION VELOCITY
                "velocity": {
                    "days_since_first_hire": days_since_first_htd_start,
                    "core_certified_per_month": (
                        round(len(core_certified) / (days_since_first_htd_start / 30), 1)
                        if days_since_first_htd_start and days_since_first_htd_start > 0
                        else 0
                    ),
                },

                # ACTION ITEMS
                "recommendations": recommendations,

                # COACHING MESSAGE
                "coaching": generate_htd_coaching(
                    bu.name,
                    len(core_certified),
                    len(all_employees),
                    len(specialty_in_htd),
                    core_forecast,
                ),
            }

            # Log to performance store for Flash audit trail
            write_performance_event(
                db,
                event_type="HTD_PIPELINE_TRACKING",
                tenant_id=tenant_id,
                event_data={
                    "bu_name": bu.name,
                    "bu_id": bu_id,
                    "core_certified": len(core_certified),
                    "specialty_in_development": len(specialty_in_htd),
                    "core_ratio_pct": result["core_ratio"]["current_pct"],
                    "core_forecast": core_forecast,
                    "recommendations_count": len(recommendations),
                    "critical_alerts": len([r for r in recommendations if r["priority"] == "CRITICAL"]),
                },
            )

            return result

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("HTD Pipeline Agent", "partners_conversion_health")
    async def partners_conversion_health(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        CEO View: All partners' SPECIALTY→CORE conversion health at a glance.

        Answers:
        - Who's converting well? Who's stuck?
        - Which BUs need HTD to bridge gaps?
        - Total CORE capacity growing on schedule?
        """
        try:
            business_units = db.query(BusinessUnit).filter(
                BusinessUnit.tenant_id == tenant_id
            ).all()

            bu_health = []

            for bu in business_units:
                employees = db.query(Employee).filter(
                    Employee.bu_id == bu.id,
                    Employee.status != "EXITED"
                ).all()

                if not employees:
                    continue

                core_count = len([e for e in employees if e.delivery_engine == "CORE"])
                specialty_htd = len([e for e in employees if e.delivery_engine == "SPECIALITY" and e.htd_track])

                bu_health.append({
                    "bu_name": bu.name,
                    "bu_id": bu.id,
                    "total_headcount": len(employees),
                    "core_certified": core_count,
                    "in_development": specialty_htd,
                    "core_pct": round(core_count / len(employees) * 100, 1) if employees else 0,
                    "htd_needed": specialty_htd == 0,  # No one in pipeline = RED FLAG
                })

            # Sort by CORE%, show who's behind
            bu_health_sorted = sorted(bu_health, key=lambda x: x["core_pct"], reverse=True)

            # Alert tier
            critical_bu = [bu for bu in bu_health if bu["htd_needed"]]
            at_risk_bu = [bu for bu in bu_health if bu["core_pct"] < 50 and bu["core_pct"] > 0]
            healthy_bu = [bu for bu in bu_health if bu["core_pct"] >= 60]

            result = {
                "status": "success",
                "date": datetime.now().date().isoformat(),
                "summary": {
                    "total_bu": len(bu_health),
                    "critical_alerts": len(critical_bu),
                    "at_risk": len(at_risk_bu),
                    "healthy": len(healthy_bu),
                },
                "bu_breakdown": bu_health_sorted,
                "critical_alerts": critical_bu,
                "at_risk_units": at_risk_bu,
                "healthy_units": healthy_bu,
            }

            # Log to performance store for daily tracking
            write_performance_event(
                db,
                event_type="HTD_PARTNERS_HEALTH_CHECK",
                tenant_id=tenant_id,
                event_data={
                    "total_bu": len(bu_health),
                    "critical_alerts": len(critical_bu),
                    "at_risk": len(at_risk_bu),
                    "healthy": len(healthy_bu),
                    "bu_breakdown": [
                        {
                            "bu_name": bu["bu_name"],
                            "bu_id": bu["bu_id"],
                            "core_pct": bu["core_pct"],
                            "core_certified": bu["core_certified"],
                        }
                        for bu in bu_health_sorted
                    ],
                },
            )

            return result

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise


def generate_htd_coaching(bu_name: str, core_count: int, total: int, developing: int, forecast: int) -> str:
    """
    Generate coaching message for BU head.

    Operating Model Principle:
    - Each BU owns its own CORE development independently
    - NO cross-BU resource borrowing
    - Solutions: (1) Accelerate gates on pipeline, (2) Hire external CORE, (3) Improve gate decisions
    """
    core_pct = (core_count / total * 100) if total > 0 else 0
    forecast_pct = (forecast / total * 100) if total > 0 else 0

    if core_pct >= 60 and developing > 0:
        return (f"🎯 {bu_name}: At target (60% CORE). "
                f"You have {core_count} CORE, {developing} developing. "
                f"Forecast: {forecast} CORE by next review. Keep momentum. "
                f"(You own this solution independently; no cross-BU borrowing.)")

    elif core_pct >= 40:
        return (f"📈 {bu_name}: On path to target. "
                f"{core_count} CORE today, forecast {forecast}. "
                f"Stay focused on gate execution. "
                f"(You own this solution independently; no cross-BU borrowing.)")

    elif core_pct >= 20:
        return (f"⚠️ {bu_name}: Below 60% CORE. "
                f"Only {core_pct:.0f}% certified. "
                f"HTD may be needed to bridge gap faster than 90-day development. "
                f"YOU must solve this: hire external, not borrow from other BUs.")

    else:
        return (f"🚨 {bu_name}: CRITICAL. "
                f"Only {core_count} CORE ({core_pct:.0f}%). "
                f"{developing} in pipeline but {forecast} forecast is low. "
                f"HTD: Hire external CORE immediately (this is YOUR responsibility, not other BUs').")
