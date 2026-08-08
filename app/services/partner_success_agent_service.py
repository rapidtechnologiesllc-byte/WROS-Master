"""
Partner Success Agent Service

NOT a tracker. A COACH.
Works FOR partners to make them successful toward their revenue targets.

Troy = $3M, Curtis = $4M, Avinash = $2M

Daily standup: "Here's what you need to do TODAY to hit $XXK"
Weekly check-in: "You're at $XXK. Need $XXK by Friday. Here's what's stalling."
Removes friction: "Your deal with Client X needs Y. I found Z. Done."

Philosophy: Partners succeed = company succeeds.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.agent_logging import log_agent_execution
from app.models.opportunities import Opportunities
from app.models.user import Users


class PartnerSuccessAgent:
    """Proactive partner coaching toward revenue targets."""

    # Partner targets (gross revenue)
    PARTNER_TARGETS = {
        "troy": 3_000_000_00,      # $3M in USD cents
        "curtis": 4_000_000_00,    # $4M
        "avinash": 2_000_000_00,   # $2M
    }

    @staticmethod
    def get_partner_key(partner_id_or_name: str) -> Optional[str]:
        """Normalize partner name to key."""
        name_lower = partner_id_or_name.lower()
        if "troy" in name_lower:
            return "troy"
        elif "curtis" in name_lower:
            return "curtis"
        elif "avinash" in name_lower:
            return "avinash"
        return None

    @staticmethod
    @log_agent_execution("Partner Success Agent", "thursday_ceo_prep")
    async def thursday_ceo_prep(
        tenant_id: str,
        partner_key: str,  # "troy", "curtis", "avinash"
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Thursday ONLY (before CEO call): Validation check-in.

        "Here's your week. Here's what you tell the CEO in 30 min."
        Not daily nagging. Just once-a-week reality check before talking to boss.
        """
        try:
            if partner_key not in PartnerSuccessAgent.PARTNER_TARGETS:
                raise ValueError(f"Unknown partner: {partner_key}")

            annual_target = PartnerSuccessAgent.PARTNER_TARGETS[partner_key]

            # Get partner's user record
            partner = db.query(Users).filter(
                Users.tenant_id == tenant_id,
                func.lower(Users.UserName).contains(partner_key)
            ).first()

            if not partner:
                raise ValueError(f"Partner {partner_key} not found")

            # Calculate progress
            today = datetime.utcnow().date()
            year_start = today.replace(month=1, day=1)
            days_into_year = (today - year_start).days + 1
            days_remaining_in_year = 365 - days_into_year

            daily_burn_rate = annual_target / 365  # Revenue per day needed
            ytd_revenue_cents = 0  # Would query actual revenue

            # Get partner's opportunities
            opportunities = db.query(Opportunities).filter(
                Opportunities.tenant_id == tenant_id,
                Opportunities.partner_id == partner.UserID,
                Opportunities.status == "open"
            ).all()

            # Calculate pipeline
            pipeline_value_cents = sum(opp.deal_size_usd_cents * opp.probability for opp in opportunities)

            # Deals by stage
            deals_by_stage = {}
            for opp in opportunities:
                stage = opp.stage
                if stage not in deals_by_stage:
                    deals_by_stage[stage] = []
                deals_by_stage[stage].append({
                    "client": opp.client_name,
                    "size_usd": opp.deal_size_usd_cents / 100,
                    "expected_close": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
                })

            # Calculate pace
            ytd_target = (annual_target / 365) * days_into_year
            ytd_pace_pct = (ytd_revenue_cents / ytd_target * 100) if ytd_target > 0 else 0

            # TODAY's action items
            action_items = []

            # Priority 1: Deals closing THIS WEEK
            week_end = today + timedelta(days=7)
            closing_this_week = [opp for opp in opportunities
                                if opp.expected_close_date and
                                today <= opp.expected_close_date <= week_end]

            for opp in closing_this_week:
                if opp.stage not in ["commitment", "closed_won"]:
                    action_items.append({
                        "priority": "CRITICAL",
                        "action": f"Move {opp.client_name} (${opp.deal_size_usd_cents/100:,.0f}) to {next_stage(opp.stage)} TODAY",
                        "reason": f"Closes {(opp.expected_close_date - today).days} days from now, currently in {opp.stage}",
                        "steps": [
                            f"Call client today (morning)",
                            f"Confirm decision/address blockers",
                            f"Get commitment or restart process",
                        ]
                    })

            # Priority 2: Stalled deals
            stalled = [opp for opp in opportunities if should_flag_stalled(opp)]
            for opp in stalled:
                action_items.append({
                    "priority": "HIGH",
                    "action": f"Restart {opp.client_name} (${opp.deal_size_usd_cents/100:,.0f}) - stalled",
                    "reason": f"No activity for {days_since_activity(opp)} days",
                    "steps": [
                        f"Call client today - ask for status",
                        f"Identify blocker (budget? decision? process?)",
                        f"Set next action (meeting? proposal revision? budget review?)",
                    ]
                })

            # Priority 3: Prospects needing qualification
            prospects = [opp for opp in opportunities if opp.stage == "prospect"]
            if prospects:
                action_items.append({
                    "priority": "MEDIUM",
                    "action": f"Qualify {len(prospects)} prospect(s) - each could be $XXK",
                    "reason": "Prospects need to move to qualified (10% → 25% probability)",
                    "steps": [
                        f"Call each prospect (5-10 min each)",
                        f"Confirm: budget approved? decision maker identified? timeline?",
                        f"Move qualified ones to 'qualified' stage",
                    ]
                })

            # Daily revenue needed
            revenue_needed_today = daily_burn_rate - (ytd_revenue_cents - ytd_target) / days_remaining_in_year if days_remaining_in_year > 0 else daily_burn_rate

            return {
                "status": "success",
                "partner": partner_key.upper(),
                "date": today.isoformat(),

                # TODAY'S PACE
                "todays_target_usd": revenue_needed_today / 100,
                "days_into_year": days_into_year,
                "days_remaining": days_remaining_in_year,
                "ytd_revenue_usd": ytd_revenue_cents / 100,
                "ytd_target_usd": ytd_target / 100,
                "ytd_pace_pct": round(ytd_pace_pct, 1),

                # PIPELINE
                "total_pipeline_usd": sum(opp.deal_size_usd_cents for opp in opportunities) / 100,
                "probability_weighted_pipeline_usd": pipeline_value_cents / 100,
                "deals_in_pipeline": len(opportunities),
                "deals_by_stage": deals_by_stage,

                # TODAY'S ACTION PLAN
                "action_items": action_items,
                "action_count": len(action_items),

                # COACHING MESSAGE
                "todays_message": f"${''.join(generate_coaching_message(partner_key, ytd_pace_pct, len(action_items)))}",

                # FORECAST
                "forecast": {
                    "on_track": ytd_pace_pct >= 85,
                    "probability": ytd_pace_pct / 100,
                    "projected_year_end_usd": (ytd_revenue_cents / days_into_year * 365) / 100 if days_into_year > 0 else 0,
                    "target_usd": annual_target / 100,
                }
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("Partner Success Agent", "weekly_business_review")
    async def weekly_business_review(
        tenant_id: str,
        partner_key: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Weekly: Coaching session. "Here's what's working. Here's what's not."
        """
        try:
            if partner_key not in PartnerSuccessAgent.PARTNER_TARGETS:
                raise ValueError(f"Unknown partner: {partner_key}")

            annual_target = PartnerSuccessAgent.PARTNER_TARGETS[partner_key]
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
            week_ago = today - timedelta(days=7)

            # Get partner
            partner = db.query(Users).filter(
                Users.tenant_id == tenant_id,
                func.lower(Users.UserName).contains(partner_key)
            ).first()

            if not partner:
                raise ValueError(f"Partner {partner_key} not found")

            # This week's activity
            opportunities = db.query(Opportunities).filter(
                Opportunities.tenant_id == tenant_id,
                Opportunities.partner_id == partner.UserID,
            ).all()

            # Deals closed this week
            closed_this_week = [opp for opp in opportunities
                               if opp.status == "closed_won" and
                               opp.updated_at >= week_start]

            closed_revenue_week = sum(opp.deal_size_usd_cents for opp in closed_this_week)

            # Deals advanced this week
            advanced_this_week = [opp for opp in opportunities
                                 if opp.updated_at >= week_ago and
                                 opp.stage in ["qualified", "proposal", "negotiation", "commitment"]]

            # What's winning
            winners = []
            if closed_this_week:
                winners.append(f"Closed {len(closed_this_week)} deal(s) for ${closed_revenue_week/100:,.0f} this week!")
            if len(advanced_this_week) > 3:
                winners.append(f"Strong pipeline momentum - {len(advanced_this_week)} deals advanced this week")

            # What needs work
            improvements = []
            open_opportunities = [opp for opp in opportunities if opp.status == "open"]
            stalled_count = len([opp for opp in open_opportunities if should_flag_stalled(opp)])
            if stalled_count > 0:
                improvements.append(f"{stalled_count} deal(s) stalled - need to restart these TODAY")

            prospects = [opp for opp in open_opportunities if opp.stage == "prospect"]
            if len(prospects) > 5:
                improvements.append(f"Too many unqualified prospects ({len(prospects)}). Qualify or drop.")

            return {
                "status": "success",
                "partner": partner_key.upper(),
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
                    f"Close at least 1 deal by Friday (hit daily pace)",
                ],

                # PARTNER COACHING
                "coaching": generate_weekly_coaching(partner_key, closed_revenue_week, stalled_count),
            }

        except Exception as e:
            raise


def next_stage(current_stage: str) -> str:
    """Get next stage in sales cycle."""
    stages = ["prospect", "qualified", "proposal", "negotiation", "commitment", "closed_won"]
    try:
        idx = stages.index(current_stage)
        return stages[idx + 1] if idx < len(stages) - 1 else current_stage
    except:
        return "qualified"


def should_flag_stalled(opp: Opportunities) -> bool:
    """Check if deal is stalled."""
    if not opp.last_activity_at:
        return False

    thresholds = {
        "prospect": 7,
        "qualified": 5,
        "proposal": 3,
        "negotiation": 2,
        "commitment": 1,
    }

    threshold = thresholds.get(opp.stage, 7)
    days_without_activity = (datetime.utcnow() - opp.last_activity_at).days
    return days_without_activity > threshold


def days_since_activity(opp: Opportunities) -> int:
    """Days since last activity."""
    if not opp.last_activity_at:
        return 999
    return (datetime.utcnow() - opp.last_activity_at).days


def generate_coaching_message(partner_key: str, pace_pct: float, action_count: int) -> str:
    """Generate daily coaching message."""
    if pace_pct >= 100:
        return f"🔥 {partner_key.upper()}: You're CRUSHING IT! {pace_pct:.0f}% of pace. Keep this energy."
    elif pace_pct >= 85:
        return f"📈 {partner_key.upper()}: On track. {pace_pct:.0f}% of pace. {action_count} items to close today."
    elif pace_pct >= 70:
        return f"⚠️ {partner_key.upper()}: Slightly behind. {pace_pct:.0f}% of pace. {action_count} critical actions TODAY."
    else:
        return f"🚨 {partner_key.upper()}: BEHIND PACE. {pace_pct:.0f}% of target. URGENT: {action_count} actions to restart deals."


def generate_weekly_coaching(partner_key: str, weekly_revenue: int, stalled_count: int) -> str:
    """Generate weekly coaching message."""
    weekly_revenue_usd = weekly_revenue / 100

    if weekly_revenue_usd > 500000:
        return f"EXCELLENT week. ${weekly_revenue_usd:,.0f} closed. Keep up this energy and focus."
    elif stalled_count == 0 and weekly_revenue_usd > 100000:
        return f"Good week. ${weekly_revenue_usd:,.0f} closed, pipeline healthy. No stalled deals."
    elif stalled_count > 2:
        return f"Mixed week. ${weekly_revenue_usd:,.0f} closed but {stalled_count} deals stalled. RESTART THESE."
    else:
        return f"Solid work. Keep your prospects moving. Get one deal to commitment by Friday."
