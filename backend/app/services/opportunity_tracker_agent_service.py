"""
Opportunity Tracker Agent Service

When a partner or sales person identifies a target client, this agent:
1. Logs the opportunity against the real client with stage, value, timeline
2. Tracks pipeline health daily (Flash orchestration calls it)
3. Flags stalls (no update past the stage's threshold -> escalate)
4. Calculates the probability-weighted pipeline
5. Validates we're on path to the annual revenue target

Built on the real Opportunity model and opportunity_service (stages
QUALIFICATION..ACTIVE/LOST, revenue_value_usd_cents, probability_pct).
There is no per-opportunity activity table, so "last activity" is
Opportunity.updated_at; logging an activity touches it.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.agent_logging import log_agent_execution
from app.models.client import Client
from app.models.employee import Employee
from app.models.opportunity import CLOSED_STAGES, Opportunity
from app.models.user import Users
from app.services.opportunity_service import (
    calculate_weighted_forecast,
    create_opportunity,
    transition_stage,
)

logger = logging.getLogger(__name__)


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


class OpportunityTrackerAgent:
    """Tracks sales opportunities and pipeline health toward the revenue target."""

    ANNUAL_REVENUE_TARGET_USD_CENTS = 100_000_000_00  # $100M

    # Days without an update before an open opportunity counts as stalled
    ACTIVITY_STALL_THRESHOLD = {
        "QUALIFICATION": 7,
        "PROSPECT": 5,
        "PROPOSAL": 3,
        "NEGOTIATION": 2,
    }
    # Stages that are not yet committed; closing within a week at one of these is a risk
    AT_RISK_STAGES = ("QUALIFICATION", "PROSPECT", "PROPOSAL", "NEGOTIATION")

    @staticmethod
    def _client_name(db: Session, client_id: str) -> Optional[str]:
        client = db.query(Client).filter(Client.id == client_id).first()
        return client.company_name if client else None

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "log_new_opportunity")
    async def log_new_opportunity(
        tenant_id,
        partner_id: str,
        client_name: str,
        deal_size_usd_cents: int,
        expected_close_date,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Log an opportunity for an existing client (matched by company name).

        partner_id is the logging user's UserID; their employee record, if
        any, becomes the opportunity owner.
        """
        # The caller's tenant only: a same-named client of another tenant is not theirs
        client = db.query(Client).filter(Client.tenant_id == tenant_id,
                                         func.lower(Client.company_name) == client_name.strip().lower()).first()
        if client is None:
            raise ValueError(f"No client named {client_name!r}; create the client first")

        existing = db.query(Opportunity).filter(
            Opportunity.client_id == client.id,
            Opportunity.stage.notin_(CLOSED_STAGES),
        ).first()
        if existing:
            return {
                "status": "duplicate",
                "opportunity_id": existing.id,
                "message": f"Open opportunity for {client.company_name} already tracked",
                "stage": existing.stage,
                "deal_size_usd": existing.revenue_value_usd_cents / 100,
            }

        owner = db.query(Employee).filter(Employee.wros_user_id == partner_id).first()
        opportunity = create_opportunity(
            db,
            tenant_id=tenant_id,
            client_id=client.id,
            revenue_value_usd_cents=deal_size_usd_cents,
            owner_employee_id=owner.id if owner else None,
            # the client's own Client Owner, else the partner who logged it
            client_owner_id=client.client_owner_user_id or partner_id,
            expected_close_date=_as_date(expected_close_date),
        )
        db.commit()
        actor = db.query(Users).filter(Users.UserID == partner_id).first()
        if actor is not None:
            from app.services.client_team_notification_service import notify_opportunity_created

            notify_opportunity_created(db, opportunity, actor=actor)
        weighted = calculate_weighted_forecast(opportunity)
        return {
            "status": "success",
            "opportunity_id": opportunity.id,
            "client_name": client.company_name,
            "deal_size_usd": deal_size_usd_cents / 100,
            "stage": opportunity.stage,
            "probability_pct": opportunity.probability_pct,
            "weighted_revenue_usd": weighted / 100,
            "expected_close_date": opportunity.expected_close_date.isoformat() if opportunity.expected_close_date else None,
            "message": f"Opportunity logged for {client.company_name}. Tracking to closure.",
        }

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "track_pipeline_health")
    async def track_pipeline_health(
        tenant_id,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Daily pipeline health check toward the annual target: weighted
        pipeline, per-stage breakdown, stalled and at-risk opportunities."""
        target = OpportunityTrackerAgent.ANNUAL_REVENUE_TARGET_USD_CENTS
        opportunities = db.query(Opportunity).filter(Opportunity.stage.notin_(CLOSED_STAGES)).all()

        if not opportunities:
            return {
                "status": "no_opportunities",
                "total_opportunities": 0,
                "pipeline_value_usd": 0,
                "target_usd": target / 100,
                "forecast_completion_pct": 0,
                "flash_action_required": True,
                "message": "No open opportunities. CRITICAL: Pipeline is empty.",
            }

        clients = {
            c.id: c for c in db.query(Client).filter(Client.id.in_({o.client_id for o in opportunities})).all()
        }
        names = {cid: c.company_name for cid, c in clients.items()}
        today = date.today()
        now = datetime.utcnow()
        pipeline_by_stage: Dict[str, Dict[str, Any]] = {}
        stalled, escalations = [], []
        total_cents = weighted_cents = 0

        for opp in opportunities:
            value = opp.revenue_value_usd_cents or 0
            weighted = calculate_weighted_forecast(opp)
            total_cents += value
            weighted_cents += weighted

            bucket = pipeline_by_stage.setdefault(opp.stage, {"count": 0, "total_usd": 0, "weighted_usd": 0})
            bucket["count"] += 1
            bucket["total_usd"] += value / 100
            bucket["weighted_usd"] += weighted / 100

            last_activity = opp.updated_at or opp.created_at
            threshold = OpportunityTrackerAgent.ACTIVITY_STALL_THRESHOLD.get(opp.stage)
            if last_activity and threshold is not None:
                idle_days = (now - last_activity).days
                if idle_days > threshold:
                    stalled.append({
                        "opportunity_id": opp.id,
                        "client_name": names.get(opp.client_id),
                        "owner_employee_id": opp.owner_employee_id,
                        "business_unit_id": getattr(clients.get(opp.client_id), "business_unit_id", None),
                        "stage": opp.stage,
                        "deal_size_usd": value / 100,
                        "days_without_activity": idle_days,
                        "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                        "severity": "critical" if idle_days > threshold * 2 else "warning",
                    })

            if opp.expected_close_date and opp.stage in OpportunityTrackerAgent.AT_RISK_STAGES:
                days_left = (opp.expected_close_date - today).days
                if days_left < 7:
                    escalations.append({
                        "opportunity_id": opp.id,
                        "client_name": names.get(opp.client_id),
                        "reason": f"Deal closes in {days_left} days but only at {opp.stage} stage",
                        "action": "Escalate to Flash for immediate intervention",
                    })

        forecast_pct = weighted_cents / target * 100
        return {
            "status": "success",
            "date": now.isoformat(),
            "total_opportunities": len(opportunities),
            "pipeline_metrics": {
                "total_pipeline_usd": total_cents / 100,
                "probability_weighted_usd": weighted_cents / 100,
                "target_usd": target / 100,
                "forecast_completion_pct": round(forecast_pct, 1),
                "gap_to_target_usd": (target - weighted_cents) / 100,
            },
            "pipeline_by_stage": pipeline_by_stage,
            "stalled_opportunities": stalled,
            "escalations_needed": escalations,
            "health_status": "on_track" if forecast_pct >= 100 else "at_risk" if forecast_pct >= 75 else "critical",
            "flash_action_required": bool(escalations or stalled),
        }

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "update_opportunity_stage")
    async def update_opportunity_stage(
        opportunity_id: str,
        new_stage: str,
        activity_note: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Move an opportunity to new_stage (opportunity_service rules apply)."""
        opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opp:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        old_stage = opp.stage
        try:
            transition_stage(db, opp, new_stage.upper())
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        db.commit()
        logger.info(f"[OpportunityTracker] {opportunity_id}: {old_stage} -> {opp.stage} ({activity_note})")
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "client_name": OpportunityTrackerAgent._client_name(db, opp.client_id),
            "old_stage": old_stage,
            "new_stage": opp.stage,
            "probability_pct": opp.probability_pct,
            "weighted_revenue_usd": calculate_weighted_forecast(opp) / 100,
            "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
        }

    @staticmethod
    @log_agent_execution("Opportunity Tracker Agent", "log_opportunity_activity")
    async def log_opportunity_activity(
        opportunity_id: str,
        activity: str,
        outcome: str,
        next_step: Optional[str],
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Record activity on an opportunity: resets its stall clock (updated_at)."""
        opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opp:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        opp.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"[OpportunityTracker] {opportunity_id} activity={activity} outcome={outcome} next={next_step}")
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "client_name": OpportunityTrackerAgent._client_name(db, opp.client_id),
            "stage": opp.stage,
            "activity": activity,
            "outcome": outcome,
            "next_step": next_step,
            "logged_at": opp.updated_at.isoformat(),
        }
