"""
Flash Orchestration Engine - Daily Command Coordination

Flash is NOT a tracker. Flash is an ORCHESTRATOR that:
1. Collects daily data from all agents (HTD Pipeline, Opportunity Tracker, Agent State)
2. Identifies bottlenecks and risks (CORE gap, stalled deals, agent underperformance)
3. Issues directives to partners and agents on what to do TODAY
4. Escalates to CEO when issues exceed partner authority

Daily workflow:
1. 8:00 AM - Agent Standup (all agents report yesterday's performance)
2. 8:05 AM - HTD Pipeline Check (CORE conversion forecast)
3. 8:10 AM - Opportunity Review (sales pipeline health, stalled deals)
4. 8:15 AM - Flash Decision Engine (analyze + issue directives)
5. 8:30 AM - Scrum of Scrums (Flash reports to CEO + Partners)

Philosophy: "We work FOR partners to enable success, not burden them with reports."
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.agent_logging import log_agent_execution
from app.models.opportunities import Opportunities
from app.models.employee import Employee
from app.models.business_units import BusinessUnit
from app.models.user import Users
from app.services.htd_pipeline_accountability_agent import HTDPipelineAccountabilityAgent
from app.services.opportunity_tracker_agent_service import OpportunityTrackerAgent
from app.services.performance_store_service import write_performance_event


class FlashOrchestrationEngine:
    """Daily coordination of all 70+ agents toward $100M revenue target."""

    @staticmethod
    @log_agent_execution("Flash Orchestration Engine", "daily_coordination")
    async def daily_flash_coordination(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Flash's daily coordination engine:
        1. Collects data from HTD Pipeline Agent, Opportunity Tracker, Agent State
        2. Identifies bottlenecks: CORE talent gap, stalled deals, agent failures
        3. Issues directives to partners on what to do TODAY
        4. Escalates critical issues to CEO

        Returns: Directives, alerts, and recommended actions for each partner.
        """
        try:
            # 1. COLLECT DATA FROM ALL AGENTS
            htd_health = await HTDPipelineAccountabilityAgent.partners_conversion_health(
                tenant_id=tenant_id,
                db=db
            )

            opportunity_health = await OpportunityTrackerAgent.track_pipeline_health(
                tenant_id=tenant_id,
                db=db
            )

            # Get all business units (partners)
            business_units = db.query(BusinessUnit).filter(
                BusinessUnit.tenant_id == tenant_id
            ).all()

            # 2. ANALYZE EACH PARTNER'S SITUATION
            partner_directives = []

            for bu in business_units:
                bu_htd = next(
                    (b for b in htd_health.get("bu_breakdown", []) if b["bu_id"] == bu.id),
                    None
                )

                if not bu_htd:
                    continue

                # GET THE CORE CONVERSION SITUATION
                core_pct = bu_htd["core_pct"]
                in_development = bu_htd["in_development"]
                total_people = bu_htd["total_headcount"]
                core_certified = bu_htd["core_certified"]

                # IDENTIFY BOTTLENECKS
                alerts = []
                directives = []

                # BOTTLENECK 1: No one in development pipeline
                if in_development == 0:
                    alerts.append({
                        "severity": "CRITICAL",
                        "type": "NO_DEVELOPMENT_PIPELINE",
                        "message": f"{bu.name}: ZERO people in HTD pipeline. No CORE talent being developed.",
                        "action": "HTD: Hire external CORE immediately. No internal pipeline to draw from.",
                    })
                    directives.append({
                        "priority": 1,
                        "directive": "HTD_HIRE_EXTERNAL_CORE",
                        "reason": f"No development pipeline. Market supply needed.",
                        "target_hire_count": max(0, int(total_people * 0.6) - core_certified),
                        "timeline_days": 30,
                    })

                # BOTTLENECK 2: Development pipeline exists but low CORE conversion forecast
                elif core_pct < 50:
                    alerts.append({
                        "severity": "HIGH",
                        "type": "CORE_DEFICIT",
                        "message": f"{bu.name}: Only {core_pct}% CORE (target: 60%). {in_development} in development but forecast too low.",
                        "action": "Accelerate HTD: Hire external + accelerate gate progression in development pipeline.",
                    })
                    directives.append({
                        "priority": 2,
                        "directive": "ACCELERATE_CORE_DEVELOPMENT",
                        "reason": f"Behind 60% CORE target at {core_pct}%.",
                        "actions": [
                            "Accelerate gate progression for people in CONTROLLED_OWNERSHIP phase",
                            "Hire 5-10 external CORE to bridge gap",
                            "Double-check gate decisions at last phase (CORE_ELIGIBILITY_REVIEW) for any quick passes",
                        ],
                    })

                # BOTTLENECK 3: Stalled opportunities (can't staff them)
                stalled_by_bu = [
                    opp for opp in opportunity_health.get("stalled_deals", [])
                    if opp.get("partner_bu_id") == bu.id
                ]

                if stalled_by_bu:
                    for opp in stalled_by_bu:
                        # Is it stalled because of CORE talent shortage?
                        if opp.get("stage") in ["proposal", "negotiation", "commitment"]:
                            # Late-stage deal stalled → likely staffing issue
                            alerts.append({
                                "severity": "HIGH",
                                "type": "STALLED_DEAL_LIKELY_STAFFING",
                                "message": f"{bu.name}: ${opp.get('deal_size_usd', 0):,} deal ({opp.get('client_name')}) stalled {opp.get('days_stalled', 0)} days. Likely need CORE staffing.",
                                "action": "Pull CORE resource from lower priority work OR recommend HTD external hire to close this deal.",
                            })

                # BOTTLENECK 4: Agent performance issues
                # TODO: Check agent state/fear levels - if recruitment or resource management agents underperforming,
                # that's why this BU can't hire/develop fast enough

                # BUILD THE DIRECTIVE FOR THIS PARTNER
                if alerts or directives:
                    partner_directives.append({
                        "bu_name": bu.name,
                        "bu_id": bu.id,
                        "current_state": {
                            "total_people": total_people,
                            "core_certified": core_certified,
                            "core_pct": core_pct,
                            "in_development": in_development,
                        },
                        "alerts": alerts,
                        "flash_directives": directives,
                    })

            # 3. ESCALATE TO CEO IF CRITICAL
            critical_count = len([a for p in partner_directives for a in p["alerts"] if a["severity"] == "CRITICAL"])
            high_count = len([a for p in partner_directives for a in p["alerts"] if a["severity"] == "HIGH"])

            ceo_escalation = None
            if critical_count > 0 or (high_count > 2):
                ceo_escalation = {
                    "severity": "ESCALATION_REQUIRED",
                    "critical_alerts": critical_count,
                    "high_alerts": high_count,
                    "recommendation": "CEO review and guidance needed on which partners to support with HTD hiring or resource redistribution.",
                }

            # Log this coordination round to performance store
            write_performance_event(
                db,
                event_type="FLASH_DAILY_COORDINATION",
                tenant_id=tenant_id,
                event_data={
                    "partners_analyzed": len(business_units),
                    "partners_with_directives": len(partner_directives),
                    "critical_alerts": critical_count,
                    "high_alerts": high_count,
                    "ceo_escalation_required": ceo_escalation is not None,
                },
            )

            return {
                "status": "success",
                "date": datetime.now().date().isoformat(),
                "time": datetime.now().time().isoformat(),
                "summary": {
                    "partners_analyzed": len(business_units),
                    "partners_requiring_action": len(partner_directives),
                    "critical_alerts": critical_count,
                    "high_alerts": high_count,
                },
                "partner_directives": partner_directives,
                "ceo_escalation": ceo_escalation,
                "flash_message": generate_flash_summary(partner_directives, critical_count, high_count),
            }

        except Exception as e:
            raise


def generate_flash_summary(directives: List[Dict], critical: int, high: int) -> str:
    """Generate Flash's daily summary message."""
    if critical > 0:
        return f"🚨 {critical} CRITICAL ALERTS require immediate CEO escalation. Directives issued to {len(directives)} partners."
    elif high > 0:
        return f"⚠️ {high} HIGH-priority issues flagged. {len(directives)} partners have action items. Monitor closely."
    elif directives:
        return f"✓ All partners have development plans. {len(directives)} active coordination items. On track."
    else:
        return "✓ All systems healthy. No immediate actions required."
