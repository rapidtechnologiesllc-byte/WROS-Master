"""
import logging
Opportunity Tracker Agent Service

When a partner or sales person identifies a target client, this agent:
1. Logs the opportunity with deal stage, size, timeline
2. Tracks progress daily/weekly
3. Flags stalls (no activity → escalate)
4. Calculates probability-weighted pipeline
5. Validates we're on path to $100M annual revenue target

Core question: "Are we tracking to close this deal on schedule?"
If not, Flash intervenes immediately.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.agent_logging import log_agent_execution
from app.models.opportunity import Opportunity
from app.core.logging import logger

logger = logging.getLogger(__name__)

class OpportunityTrackerAgent:
    """Tracks sales opportunities and pipeline health toward $100M target."""

    # Revenue targets
    ANNUAL_REVENUE_TARGET_USD_CENTS = 100_000_000_00  # $100M

    # Deal stage progression (standard sales cycle)
    DEAL_STAGES = [
        "prospect",       # Initial identification
        "qualified",      # Need confirmed, budget allocated
        "proposal",       # Formal proposal submitted
        "negotiation",    # Actively negotiating
        "commitment",     # Verbal commitment / LOI signed
        "closed_won",     # Contract signed, revenue recognized
        "closed_lost",    # Opportunity lost
    ]

    # Stage to probability mapping
    STAGE_PROBABILITY = {
        "prospect": 0.10,
        "qualified": 0.25,
        "proposal": 0.40,
        "negotiation": 0.65,
        "commitment": 0.85,
        "closed_won": 1.00,
        "closed_lost": 0.00,
    }

    # Days between expected activity by stage
    ACTIVITY_STALL_THRESHOLD = {
        "prospect": 7,         # Expect contact within 7 days
        "qualified": 5,        # Tighter once qualified
        "proposal": 3,         # Active negotiation = daily contact
        "negotiation": 2,
        "commitment": 1,       # Close is imminent
    }

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "log_new_opportunity")
    async def log_new_opportunity(
        tenant_id: str,
        partner_id: str,
        client_name: str,
        deal_size_usd_cents: int,
        expected_close_date: datetime,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Partner/sales person identifies target client.
        System logs opportunity and tracks to closure.

        Args:
            tenant_id: Organization
            partner_id: Partner/sales person who identified opportunity
            client_name: Target client name
            deal_size_usd_cents: Deal size in USD cents
            expected_close_date: Expected close date
            db: Database session

        Returns:
            Opportunity object with tracking initialized
        """
        try:
            # Check if opportunity already exists for this client/partner
            existing = db.query(Opportunities).filter(
                Opportunity.tenant_id == tenant_id,
                Opportunity.client_name == client_name,
                Opportunity.partner_id == partner_id,
                Opportunity.stage.in_(["prospect", "qualified", "proposal", "negotiation", "commitment"])
            ).first()

            if existing:
                return {
                    "status": "duplicate",
                    "opportunity_id": existing.id,
                    "message": f"Opportunity for {client_name} already tracked",
                    "stage": existing.stage,
                    "deal_size_usd": existing.deal_size_usd_cents / 100,
                }

            # Create new opportunity
            opportunity = Opportunities(
                tenant_id=tenant_id,
                partner_id=partner_id,
                client_name=client_name,
                deal_size_usd_cents=deal_size_usd_cents,
                stage="prospect",  # Always start at prospect
                probability=OpportunityTrackerAgent.STAGE_PROBABILITY["prospect"],
                expected_close_date=expected_close_date,
                created_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                days_in_stage=0,
                status="open"
            )
            db.add(opportunity)
            db.commit()

            return {
                "status": "success",
                "opportunity_id": opportunity.id,
                "client_name": client_name,
                "deal_size_usd": deal_size_usd_cents / 100,
                "stage": "prospect",
                "probability": 0.10,
                "weighted_revenue_usd": (deal_size_usd_cents * 0.10) / 100,
                "expected_close_date": expected_close_date.isoformat(),
                "message": f"Opportunity logged for {client_name}. Tracking to closure.",
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "track_pipeline_health")
    async def track_pipeline_health(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Daily pipeline health check toward $100M annual target.

        Returns:
        - Total pipeline value (probability-weighted)
        - Pipeline by stage
        - Stalled opportunities (no activity > threshold)
        - Forecast vs target
        - Escalations needed
        """
        try:
            # Get all open opportunities
            opportunities = db.query(Opportunities).filter(
                Opportunity.tenant_id == tenant_id,
                Opportunity.status == "open"
            ).all()

            if not opportunities:
                return {
                    "status": "no_opportunities",
                    "total_opportunities": 0,
                    "pipeline_value_usd": 0,
                    "target_usd": OpportunityTrackerAgent.ANNUAL_REVENUE_TARGET_USD_CENTS / 100,
                    "forecast_completion_pct": 0,
                    "message": "No open opportunities. CRITICAL: Pipeline is empty."
                }

            # Calculate pipeline metrics
            pipeline_by_stage = {}
            stalled_opportunities = []
            escalations_needed = []
            total_pipeline_usd_cents = 0
            total_probability_weighted_usd_cents = 0

            for opp in opportunities:
                stage = opp.stage
                deal_size = opp.deal_size_usd_cents
                probability = OpportunityTrackerAgent.STAGE_PROBABILITY.get(stage, 0)
                weighted_value = deal_size * probability

                total_pipeline_usd_cents += deal_size
                total_probability_weighted_usd_cents += weighted_value

                # Track by stage
                if stage not in pipeline_by_stage:
                    pipeline_by_stage[stage] = {
                        "count": 0,
                        "total_usd": 0,
                        "weighted_usd": 0,
                    }
                pipeline_by_stage[stage]["count"] += 1
                pipeline_by_stage[stage]["total_usd"] += deal_size / 100
                pipeline_by_stage[stage]["weighted_usd"] += weighted_value / 100

                # Check for stalls
                if opp.last_activity_at:
                    days_since_activity = (datetime.utcnow() - opp.last_activity_at).days
                    threshold = OpportunityTrackerAgent.ACTIVITY_STALL_THRESHOLD.get(stage, 7)

                    if days_since_activity > threshold:
                        stalled_opportunities.append({
                            "opportunity_id": opp.id,
                            "client_name": opp.client_name,
                            "partner_id": opp.partner_id,
                            "stage": stage,
                            "deal_size_usd": deal_size / 100,
                            "days_without_activity": days_since_activity,
                            "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                            "severity": "critical" if days_since_activity > (threshold * 2) else "warning"
                        })

                # Check if deal is at risk
                if opp.expected_close_date and (opp.expected_close_date - datetime.utcnow()).days < 7:
                    if stage not in ["commitment", "closed_won"]:
                        escalations_needed.append({
                            "opportunity_id": opp.id,
                            "client_name": opp.client_name,
                            "reason": f"Deal closes in {(opp.expected_close_date - datetime.utcnow()).days} days but only at {stage} stage",
                            "action": "Escalate to Flash for immediate intervention"
                        })

            # Calculate forecast
            forecast_pct = (total_probability_weighted_usd_cents / OpportunityTrackerAgent.ANNUAL_REVENUE_TARGET_USD_CENTS) * 100

            return {
                "status": "success",
                "date": datetime.utcnow().isoformat(),
                "total_opportunities": len(opportunities),
                "pipeline_metrics": {
                    "total_pipeline_usd": total_pipeline_usd_cents / 100,
                    "probability_weighted_usd": total_probability_weighted_usd_cents / 100,
                    "target_usd": OpportunityTrackerAgent.ANNUAL_REVENUE_TARGET_USD_CENTS / 100,
                    "forecast_completion_pct": round(forecast_pct, 1),
                    "gap_to_target_usd": (OpportunityTrackerAgent.ANNUAL_REVENUE_TARGET_USD_CENTS - total_probability_weighted_usd_cents) / 100,
                },
                "pipeline_by_stage": pipeline_by_stage,
                "stalled_opportunities": stalled_opportunities,
                "escalations_needed": escalations_needed,
                "health_status": "on_track" if forecast_pct >= 100 else "at_risk" if forecast_pct >= 75 else "critical",
                "flash_action_required": len(escalations_needed) > 0 or len(stalled_opportunities) > 0,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "update_opportunity_stage")
    async def update_opportunity_stage(
        opportunity_id: str,
        new_stage: str,
        activity_note: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update opportunity to next stage when deal progresses.
        Auto-logs activity timestamp.

        Returns validation of stage progression.
        """
        try:
            opp = db.query(Opportunities).filter(
                Opportunity.id == opportunity_id
            ).first()

            if not opp:
                raise ValueError(f"Opportunity {opportunity_id} not found")

            if new_stage not in OpportunityTrackerAgent.DEAL_STAGES:
                raise ValueError(f"Invalid stage: {new_stage}")

            # Validate progression (no backwards movement)
            current_stage_index = OpportunityTrackerAgent.DEAL_STAGES.index(opp.stage)
            new_stage_index = OpportunityTrackerAgent.DEAL_STAGES.index(new_stage)

            if new_stage_index < current_stage_index and new_stage != "closed_lost":
                raise ValueError(f"Cannot move backward from {opp.stage} to {new_stage}")

            # Update opportunity
            old_stage = opp.stage
            opp.stage = new_stage
            opp.probability = OpportunityTrackerAgent.STAGE_PROBABILITY.get(new_stage, 0)
            opp.last_activity_at = datetime.utcnow()
            opp.days_in_stage = 0

            # Add activity log
            opp.activity_history = opp.activity_history or []
            opp.activity_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "action": f"Stage updated: {old_stage} → {new_stage}",
                "note": activity_note,
            })

            db.commit()

            return {
                "status": "success",
                "opportunity_id": opportunity_id,
                "client_name": opp.client_name,
                "old_stage": old_stage,
                "new_stage": new_stage,
                "probability": opp.probability,
                "weighted_revenue_usd": (opp.deal_size_usd_cents * opp.probability) / 100,
                "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "log_opportunity_activity")
    async def log_opportunity_activity(
        opportunity_id: str,
        activity: str,  # "call", "email", "meeting", "proposal_sent", etc.
        outcome: str,   # "positive", "neutral", "negative"
        next_step: Optional[str],
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Log activity on opportunity (call, email, meeting, etc.)
        Updates last_activity_at timestamp.
        System uses this to detect stalls.
        """
        try:
            opp = db.query(Opportunities).filter(
                Opportunity.id == opportunity_id
            ).first()

            if not opp:
                raise ValueError(f"Opportunity {opportunity_id} not found")

            opp.last_activity_at = datetime.utcnow()
            opp.activity_history = opp.activity_history or []
            opp.activity_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "activity": activity,
                "outcome": outcome,
                "next_step": next_step,
            })

            db.commit()

            return {
                "status": "success",
                "opportunity_id": opportunity_id,
                "activity": activity,
                "outcome": outcome,
                "activity_logged": True,
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise
