"""
Partner Success Agent Service

NOT a tracker. A COACH.
Works FOR partners to make them successful toward their revenue targets.

The partner is any user the BU structure names as partner (BusinessUnit.partner_user_id);
their annual target is what the Goals screen holds for them this fiscal year -- never a
name or a number in code.

Daily standup: "Here's what you need to do TODAY to hit $XXK"
Weekly check-in: "You're at $XXK. Need $XXK by Friday. Here's what's stalling."
Removes friction: "Your deal with Client X needs Y. I found Z. Done."

Philosophy: Partners succeed = company succeeds.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

from app.core.agent_logging import log_agent_execution
from app.models.client import Client
from app.models.opportunity import CLOSED_STAGES, Opportunity
from app.services.finance_agent import partner_bu_ids
from app.services.opportunity_service import calculate_weighted_forecast
from app.services.opportunity_tracker_agent_service import OpportunityTrackerAgent
from app.models.user import Users

logger = logging.getLogger(__name__)

from app.models.opportunity import WON_STAGES  # noqa: E402 -- one definition of a win


def _partner_opportunities(db: Session, partner_user_id: str, open_only: bool):
    """Opportunities the partner owns directly or that sit in BUs they head.
    Returns (opportunities, {client_id: company_name})."""
    bu_ids = partner_bu_ids(db, partner_user_id)
    owned = Opportunity.client_owner_id == partner_user_id
    in_bus = Opportunity.client_id.in_(select(Client.id).where(Client.business_unit_id.in_(bu_ids)))
    query = db.query(Opportunity).filter(or_(owned, in_bus) if bu_ids else owned)
    if open_only:
        query = query.filter(Opportunity.stage.notin_(CLOSED_STAGES))
    opportunities = query.all()
    names = dict(
        db.query(Client.id, Client.company_name).filter(Client.id.in_({o.client_id for o in opportunities})).all()
    ) if opportunities else {}
    return opportunities, names


def _partner_ytd_revenue_cents(db: Session, partner_user_id: str, year_start) -> int:
    """Invoiced (approved/sent/paid) revenue this fiscal year in the partner's BUs."""
    from app.services.finance_agent import _invoice_cents
    bu_ids = partner_bu_ids(db, partner_user_id)
    return _invoice_cents(db, bu_ids, datetime.combine(year_start, datetime.min.time())) if bu_ids else 0


def _partner_and_target(db: Session, tenant_id: int, partner_user_id: str):
    """(partner user, annual revenue target in USD cents, FY start date, FY end date).

    The partner must partner at least one business unit. The target is the partner's FY
    revenue target on the Goals screen (PARTNER rows, one per company), else the sum of
    their BUs' targets there. No target set -> ValueError: coaching against an invented
    number would be worse than none."""
    from app.models.strategic_goal import GoalTarget
    from app.services.fiscal_year_service import current_fy, fy_window

    partner = db.query(Users).filter(Users.UserID == partner_user_id, Users.tenant_id == tenant_id).first()
    bu_ids = partner_bu_ids(db, partner_user_id) if partner else []
    if not partner or not bu_ids:
        raise ValueError(f"User {partner_user_id} is not the partner of any business unit")

    fy = current_fy(db, tenant_id)
    rows = db.query(GoalTarget).filter(GoalTarget.tenant_id == tenant_id, GoalTarget.year == fy,
                                       GoalTarget.metric == "revenue")
    partner_rows = [r for r in rows.filter(GoalTarget.level == "PARTNER")
                    if r.entity_id.partition(":")[2] == partner_user_id]
    bu_rows = [r for r in rows.filter(GoalTarget.level == "BU")
               if r.entity_id.partition(":")[2] in {str(i) for i in bu_ids}]
    target_usd = sum(r.target for r in partner_rows) or sum(r.target for r in bu_rows)
    if not target_usd:
        raise ValueError(f"No FY{fy} revenue target is set for {partner.UserName} on the Goals screen")
    start, end = fy_window(db, fy, tenant_id)
    return partner, int(round(target_usd * 100)), start.date(), (end - timedelta(days=1)).date()


class PartnerSuccessAgent:
    """Proactive partner coaching toward revenue targets."""

    @staticmethod
    @log_agent_execution("Partner Success Agent", "thursday_ceo_prep")
    async def thursday_ceo_prep(
        *,
        tenant_id: int,
        partner_user_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Thursday ONLY (before CEO call): Validation check-in.

        "Here's your week. Here's what you tell the CEO in 30 min."
        Not daily nagging. Just once-a-week reality check before talking to boss.
        """
        try:
            partner, annual_target, year_start, year_end = _partner_and_target(db, tenant_id, partner_user_id)

            # Calculate progress through the fiscal year
            today = datetime.utcnow().date()
            days_in_year = (year_end - year_start).days + 1
            days_into_year = (today - year_start).days + 1
            days_remaining_in_year = days_in_year - days_into_year

            daily_burn_rate = annual_target / days_in_year  # Revenue per day needed
            ytd_revenue_cents = _partner_ytd_revenue_cents(db, partner.UserID, year_start)

            # Get partner's open opportunities
            opportunities, names = _partner_opportunities(db, partner.UserID, open_only=True)

            # Calculate pipeline
            pipeline_value_cents = sum(calculate_weighted_forecast(opp) for opp in opportunities)

            # Deals by stage
            deals_by_stage = {}
            for opp in opportunities:
                stage = opp.stage
                if stage not in deals_by_stage:
                    deals_by_stage[stage] = []
                deals_by_stage[stage].append({
                    "client": names.get(opp.client_id),
                    "size_usd": opp.revenue_value_usd_cents / 100,
                    "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                })

            # Calculate pace
            ytd_target = daily_burn_rate * days_into_year
            ytd_pace_pct = (ytd_revenue_cents / ytd_target * 100) if ytd_target > 0 else 0

            # TODAY's action items
            action_items = []

            # Priority 1: Deals closing THIS WEEK
            week_end = today + timedelta(days=7)
            closing_this_week = [opp for opp in opportunities
                                if opp.expected_close_date and
                                today <= opp.expected_close_date <= week_end]

            for opp in closing_this_week:
                if opp.stage not in ("CONTRACT", "ACTIVE"):
                    action_items.append({
                        "priority": "CRITICAL",
                        "action": f"Move {names.get(opp.client_id)} (${opp.revenue_value_usd_cents/100:,.0f}) to {next_stage(opp.stage)} TODAY",
                        "reason": f"Closes {(opp.expected_close_date - today).days} days from now, currently in {opp.stage}",
                        "steps": [
                            "Call client today (morning)",
                            "Confirm decision/address blockers",
                            "Get commitment or restart process",
                        ]
                    })

            # Priority 2: Stalled deals
            stalled = [opp for opp in opportunities if should_flag_stalled(opp)]
            for opp in stalled:
                action_items.append({
                    "priority": "HIGH",
                    "action": f"Restart {names.get(opp.client_id)} (${opp.revenue_value_usd_cents/100:,.0f}) - stalled",
                    "reason": f"No activity for {days_since_activity(opp)} days",
                    "steps": [
                        "Call client today - ask for status",
                        "Identify blocker (budget? decision? process?)",
                        "Set next action (meeting? proposal revision? budget review?)",
                    ]
                })

            # Priority 3: Prospects needing qualification
            prospects = [opp for opp in opportunities if opp.stage == "QUALIFICATION"]
            if prospects:
                action_items.append({
                    "priority": "MEDIUM",
                    "action": f"Qualify {len(prospects)} prospect(s) - each could be $XXK",
                    "reason": "Prospects need to move to qualified (10% → 25% probability)",
                    "steps": [
                        "Call each prospect (5-10 min each)",
                        "Confirm: budget approved? decision maker identified? timeline?",
                        "Move qualified ones to the PROSPECT stage",
                    ]
                })

            # Daily revenue needed
            revenue_needed_today = daily_burn_rate - (ytd_revenue_cents - ytd_target) / days_remaining_in_year if days_remaining_in_year > 0 else daily_burn_rate

            return {
                "status": "success",
                "partner_user_id": partner.UserID,
                "partner": partner.UserName,
                "date": today.isoformat(),

                # TODAY'S PACE
                "todays_target_usd": revenue_needed_today / 100,
                "days_into_year": days_into_year,
                "days_remaining": days_remaining_in_year,
                "ytd_revenue_usd": ytd_revenue_cents / 100,
                "ytd_target_usd": ytd_target / 100,
                "ytd_pace_pct": round(ytd_pace_pct, 1),

                # PIPELINE
                "total_pipeline_usd": sum(opp.revenue_value_usd_cents for opp in opportunities) / 100,
                "probability_weighted_pipeline_usd": pipeline_value_cents / 100,
                "deals_in_pipeline": len(opportunities),
                "deals_by_stage": deals_by_stage,

                # TODAY'S ACTION PLAN
                "action_items": action_items,
                "action_count": len(action_items),

                # COACHING MESSAGE
                "todays_message": generate_coaching_message(partner.UserName, ytd_pace_pct, len(action_items)),

                # FORECAST
                "forecast": {
                    "on_track": ytd_pace_pct >= 85,
                    "probability": ytd_pace_pct / 100,
                    "projected_year_end_usd": (ytd_revenue_cents / days_into_year * days_in_year) / 100 if days_into_year > 0 else 0,
                    "target_usd": annual_target / 100,
                }
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_agent_execution("Partner Success Agent", "weekly_business_review")
    async def weekly_business_review(
        *,
        tenant_id: int,
        partner_user_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Weekly: Coaching session. "Here's what's working. Here's what's not."
        """
        try:
            partner, _, _, _ = _partner_and_target(db, tenant_id, partner_user_id)
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
            week_ago = today - timedelta(days=7)

            # This week's activity
            opportunities, names = _partner_opportunities(db, partner.UserID, open_only=False)

            # Deals closed this week
            closed_this_week = [opp for opp in opportunities
                               if opp.stage in WON_STAGES and
                               opp.updated_at >= week_start]

            closed_revenue_week = sum(opp.revenue_value_usd_cents for opp in closed_this_week)

            # Deals advanced this week
            advanced_this_week = [opp for opp in opportunities
                                 if opp.updated_at >= week_ago and
                                 opp.stage in ["PROSPECT", "PROPOSAL", "NEGOTIATION", "CONTRACT"]]

            # What's winning
            winners = []
            if closed_this_week:
                winners.append(f"Closed {len(closed_this_week)} deal(s) for ${closed_revenue_week/100:,.0f} this week!")
            if len(advanced_this_week) > 3:
                winners.append(f"Strong pipeline momentum - {len(advanced_this_week)} deals advanced this week")

            # What needs work
            improvements = []
            open_opportunities = [opp for opp in opportunities if opp.stage not in CLOSED_STAGES]
            stalled_count = len([opp for opp in open_opportunities if should_flag_stalled(opp)])
            if stalled_count > 0:
                improvements.append(f"{stalled_count} deal(s) stalled - need to restart these TODAY")

            prospects = [opp for opp in open_opportunities if opp.stage == "QUALIFICATION"]
            if len(prospects) > 5:
                improvements.append(f"Too many unqualified prospects ({len(prospects)}). Qualify or drop.")

            return {
                "status": "success",
                "partner_user_id": partner.UserID,
                "partner": partner.UserName,
                "week": f"{week_start.isoformat()} to {today.isoformat()}",

                # WINS
                "wins": winners,

                # AREAS FOR IMPROVEMENT
                "improvements": improvements,

                # KEY METRICS
                "this_week": {
                    "deals_closed": len(closed_this_week),
                    "revenue_closed_usd": closed_revenue_week / 100,
                    "deals_advanced": len(advanced_this_week),
                },

                # WEEKLY ACTION PLAN
                "weekly_focus": [
                    f"Get {stalled_count} stalled deals moving again",
                    f"Qualify {len(prospects)} prospects or drop them",
                    "Close at least 1 deal by Friday (hit daily pace)",
                ],

                # PARTNER COACHING
                "coaching": generate_weekly_coaching(closed_revenue_week, stalled_count),
            }

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            raise

def next_stage(current_stage: str) -> str:
    """Get next stage in sales cycle."""
    stages = ["QUALIFICATION", "PROSPECT", "PROPOSAL", "NEGOTIATION", "CONTRACT", "ACTIVE"]
    if current_stage not in stages:
        return "PROSPECT"
    idx = stages.index(current_stage)
    return stages[idx + 1] if idx < len(stages) - 1 else current_stage

def should_flag_stalled(opp: Opportunity) -> bool:
    """Check if deal is stalled."""
    threshold = OpportunityTrackerAgent.ACTIVITY_STALL_THRESHOLD.get(opp.stage)
    if threshold is None:
        return False
    return days_since_activity(opp) > threshold

def days_since_activity(opp: Opportunity) -> int:
    """Days since last activity."""
    last_activity = opp.updated_at or opp.created_at
    if not last_activity:
        return 999
    return (datetime.utcnow() - last_activity).days

def generate_coaching_message(partner_name: str, pace_pct: float, action_count: int) -> str:
    """Generate daily coaching message."""
    if pace_pct >= 100:
        return f"🔥 {partner_name}: You're CRUSHING IT! {pace_pct:.0f}% of pace. Keep this energy."
    elif pace_pct >= 85:
        return f"📈 {partner_name}: On track. {pace_pct:.0f}% of pace. {action_count} items to close today."
    elif pace_pct >= 70:
        return f"⚠️ {partner_name}: Slightly behind. {pace_pct:.0f}% of pace. {action_count} critical actions TODAY."
    else:
        return f"🚨 {partner_name}: BEHIND PACE. {pace_pct:.0f}% of target. URGENT: {action_count} actions to restart deals."

def generate_weekly_coaching(weekly_revenue: int, stalled_count: int) -> str:
    """Generate weekly coaching message."""
    weekly_revenue_usd = weekly_revenue / 100

    if weekly_revenue_usd > 500000:
        return f"EXCELLENT week. ${weekly_revenue_usd:,.0f} closed. Keep up this energy and focus."
    elif stalled_count == 0 and weekly_revenue_usd > 100000:
        return f"Good week. ${weekly_revenue_usd:,.0f} closed, pipeline healthy. No stalled deals."
    elif stalled_count > 2:
        return f"Mixed week. ${weekly_revenue_usd:,.0f} closed but {stalled_count} deals stalled. RESTART THESE."
    else:
        return "Solid work. Keep your prospects moving. Get one deal to commitment by Friday."
