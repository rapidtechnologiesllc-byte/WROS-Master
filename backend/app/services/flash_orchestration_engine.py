"""
import logging
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

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.agent_logging import log_agent_execution
from app.models.opportunity import Opportunity
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.models.candidate import Candidate
from app.services.htd_pipeline_accountability_agent import HTDPipelineAccountabilityAgent
from app.services.opportunity_tracker_agent_service import OpportunityTrackerAgent
from app.services.relation_building_agent_service import RelationBuildingAgent
from app.services.performance_store_service import write_performance_event

logger = logging.getLogger(__name__)

class FlashOrchestrationEngine:
    """Daily coordination of all 70+ agents toward $100M revenue target.

    ABSOLUTE RULE: NO CROSS-BU RESOURCE SHARING EVER.

    Each business unit solves its own bottlenecks independently:
    - If AXION needs CORE capacity → AXION hires/trains/develops
    - If PRISM needs CORE capacity → PRISM hires/trains/develops
    - SPECIALTY supports both BUs' pipelines but doesn't substitute for BU autonomy

    Every directive is validated to ensure it respects this rule.
    """

    @staticmethod
    def validate_no_cross_bu_borrowing(directive: Dict[str, Any]) -> bool:
        """
        Validate that a directive doesn't violate the NO CROSS-BU RESOURCE SHARING rule.

        Forbidden patterns:
        - "support other BUs"
        - "borrow from another BU"
        - "pull resources from another BU"
        - Any suggestion of inter-BU resource movement

        Returns: True if directive is valid (no cross-BU borrowing), False otherwise.
        """
        forbidden_phrases = [
            "support other", "borrow", "pull from", "share with", "cross-bu",
            "help another", "assist other", "backup from", "redistribute",
        ]

        directive_str = str(directive).lower()
        for phrase in forbidden_phrases:
            if phrase in directive_str:
                return False

        return True

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

            # 1b. RELATION BUILDING AGENT - Extract personas for recent candidates
            recent_candidates = db.query(Candidate).filter(
                Candidate.tenant_id == tenant_id,
                Candidate.created_at >= datetime.now() - timedelta(days=1)
            ).all()

            candidate_relationships = []
            for candidate in recent_candidates[:50]:  # Max 50 per day to avoid overload
                persona_result = await RelationBuildingAgent.extract_candidate_persona(
                    candidate_id=candidate.candidateID,
                    tenant_id=tenant_id,
                    db=db
                )
                if persona_result["status"] == "success":
                    candidate_relationships.append(persona_result)

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
                        "action": f"{bu.name} owns solution: HTD hire external CORE immediately. No internal pipeline to draw from.",
                    })
                    directives.append({
                        "priority": 1,
                        "directive": "HTD_HIRE_EXTERNAL_CORE",
                        "reason": f"No development pipeline. {bu.name} must source external market supply.",
                        "target_hire_count": max(0, int(total_people * 0.6) - core_certified),
                        "timeline_days": 30,
                        "bu_autonomous": True,
                        "cross_bu_forbidden": "NO: This is {bu.name}'s independent responsibility. Do not borrow from other BUs.",
                    })

                # BOTTLENECK 2: Development pipeline exists but low CORE conversion forecast
                elif core_pct < 50:
                    alerts.append({
                        "severity": "HIGH",
                        "type": "CORE_DEFICIT",
                        "message": f"{bu.name}: Only {core_pct}% CORE (target: 60%). {in_development} in development but forecast too low.",
                        "action": f"{bu.name} owns solution: Accelerate HTD (hire external + gate progression)",
                    })
                    directives.append({
                        "priority": 2,
                        "directive": "ACCELERATE_CORE_DEVELOPMENT",
                        "reason": f"{bu.name} behind 60% CORE target at {core_pct}%. {bu.name} must solve independently.",
                        "actions": [
                            "Accelerate gate progression for people in CONTROLLED_OWNERSHIP phase",
                            "Hire 5-10 external CORE to bridge gap",
                            "Double-check gate decisions at last phase (CORE_ELIGIBILITY_REVIEW) for any quick passes",
                        ],
                        "bu_autonomous": True,
                        "cross_bu_forbidden": f"NO: {bu.name} solves its own CORE deficit. No borrowing from other BUs allowed.",
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
                                "message": f"{bu.name}: ${opp.get('deal_size_usd', 0):,} deal ({opp.get('client_name')}) stalled {opp.get('days_stalled', 0)} days. CORE staffing constraint likely.",
                                "action": f"{bu.name} owns solution: (A) Reallocate CORE from lower priority {bu.name} work, OR (B) {bu.name} HTD external hire to close deal",
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

            # 3. VALIDATE ALL DIRECTIVES — NO CROSS-BU RESOURCE BORROWING
            for partner_directive in partner_directives:
                for directive in partner_directive.get("flash_directives", []):
                    if not FlashOrchestrationEngine.validate_no_cross_bu_borrowing(directive):
                        raise ValueError(
                            f"INVALID DIRECTIVE: Cross-BU borrowing detected in {partner_directive['bu_name']} directive: {directive}. "
                            f"RULE: Each BU solves its own capacity gaps independently. No cross-BU resource sharing allowed."
                        )

            # 4. ESCALATE TO CEO IF CRITICAL
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

            # Analyze candidate relationship quality
            candidate_relationship_summary = FlashOrchestrationEngine._summarize_candidate_relationships(
                candidate_relationships
            )

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
                    "candidates_processed": len(candidate_relationships),
                    "ceo_escalation_required": ceo_escalation is not None,
                    "candidate_relationship_quality": candidate_relationship_summary.get("avg_engagement"),
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
                    "candidates_processed": len(candidate_relationships),
                },
                "partner_directives": partner_directives,
                "candidate_relationship_intelligence": candidate_relationship_summary,
                "ceo_escalation": ceo_escalation,
                "flash_message": generate_flash_summary(partner_directives, critical_count, high_count),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _summarize_candidate_relationships(candidate_results: List[Dict]) -> Dict[str, Any]:
        """
        Summarize candidate relationship intelligence for Flash coordination.

        Analyzes:
        - Overall engagement readiness of candidate pool
        - Risk factor distribution
        - Skill depth across pool
        - Recommended engagement strategies
        """
        if not candidate_results:
            return {
                "candidates_processed": 0,
                "avg_engagement": "N/A",
                "risk_distribution": {},
                "summary": "No recent candidates to analyze",
            }

        engagements = [r["persona"]["engagement_readiness"] for r in candidate_results if "persona" in r]
        career_levels = [r["persona"]["career_level"] for r in candidate_results if "persona" in r]

        # Engagement distribution
        engagement_dist = {
            "high": len([e for e in engagements if e == "high"]),
            "medium": len([e for e in engagements if e == "medium"]),
            "low": len([e for e in engagements if e == "low"]),
        }

        # Career level distribution
        career_dist = {}
        for level in ["entry", "mid", "senior", "lead", "principal"]:
            career_dist[level] = len([c for c in career_levels if c == level])

        # Average engagement
        total = sum(engagement_dist.values())
        if total > 0:
            high_pct = (engagement_dist["high"] / total) * 100
            avg_engagement = "high" if high_pct >= 60 else "medium" if high_pct >= 30 else "low"
        else:
            avg_engagement = "unknown"

        # Risk distribution
        all_risks = []
        for result in candidate_results:
            if "persona" in result:
                all_risks.extend(result["persona"].get("risk_factors", []))

        risk_dist = {}
        for risk in all_risks:
            risk_dist[risk] = risk_dist.get(risk, 0) + 1

        return {
            "candidates_processed": len(candidate_results),
            "avg_engagement": avg_engagement,
            "engagement_distribution": engagement_dist,
            "career_level_distribution": career_dist,
            "risk_factor_distribution": risk_dist,
            "high_engagement_candidates": engagement_dist.get("high", 0),
            "candidates_needing_nurture": engagement_dist.get("low", 0),
            "summary": f"Pool: {len(candidate_results)} candidates. Engagement: {high_pct:.0f}% high. "
                      f"Career mix: {career_dist}. Top risks: {list(risk_dist.keys())[:3]}",
        }


def generate_flash_summary(directives: List[Dict], critical: int, high: int) -> str:
    """
    Generate Flash's daily summary message.

    Operating Model Principle: Every directive enforces that each BU solves its own
    bottlenecks independently. There is NO cross-BU resource borrowing, ever.
    """
    if critical > 0:
        return f"🚨 {critical} CRITICAL ALERTS require immediate CEO escalation. Directives issued to {len(directives)} partners (each owns their own solution)."
    elif high > 0:
        return f"⚠️ {high} HIGH-priority issues flagged. {len(directives)} partners have action items (autonomous solutions). Monitor closely."
    elif directives:
        return f"✓ All partners have development plans. {len(directives)} active coordination items. Each BU owns its solution. On track."
    else:
        return "✓ All systems healthy. No immediate actions required."
