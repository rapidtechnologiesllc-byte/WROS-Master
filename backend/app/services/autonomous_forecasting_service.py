"""Autonomous Forecasting & Feedback Service
Connects KPIs → Resource Needs → Escalation → Decision Tracking → Feedback Loop
This is how the system knows WHAT to ask humans for and TELLS them when they're wrong
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.kpi_service import KPIService

class AutonomousForecastingService:
    """
    The system's thinking layer:
    1. Monitor KPIs
    2. Forecast what's needed to fix
    3. Escalate to right person
    4. Track decisions
    5. Reject/warn on policy violations
    6. Autonomously inform humans they're wrong
    """

    @staticmethod
    def forecast_recruitment_needs(
        db: Session,
        phalanx: str = "recruitment"
    ) -> Dict[str, Any]:
        """
        Monitor recruitment KPIs and forecast hiring needs

        Example output:
        "Candidates sourced at 45/100 (45%). At current pace will reach 80.
         Need 20 more candidates. Requires: +2 recruiters OR +$50K Thunder budget OR 30-day delay"
        """
        try:
            # Get current KPIs
            kpi = KPIService.calculate_kpi(db, phalanx, "candidates_sourced", "weekly")

            if not kpi:
                return {"status": "no_data"}

            value = kpi.get("value", 0)
            target = kpi.get("target", 100)
            achievement = (value / target * 100) if target > 0 else 0

            # Forecast
            forecast = {
                "forecast_id": str(uuid4()),
                "phalanx": phalanx,
                "current_state": {
                    "candidates_sourced": value,
                    "target": target,
                    "achievement_percent": round(achievement, 2)
                },
                "gap_analysis": {
                    "candidates_needed": target - value,
                    "current_pace_per_week": value / 4,  # Assumes 4 weeks so far
                    "weeks_to_reach_target_at_current_pace": (target - value) / max(value / 4, 1),
                    "status": "ON_TRACK" if achievement >= 80 else "BEHIND" if achievement >= 50 else "CRITICAL"
                },
                "resource_options": [
                    {
                        "option": "INCREASE_RECRUITMENT_BUDGET",
                        "cost": "$50,000",
                        "expected_result": "+50 candidates/quarter (5x acceleration)",
                        "timeline": "Immediate",
                        "requires_approval_from": "CFO"
                    },
                    {
                        "option": "HIRE_ADDITIONAL_RECRUITER",
                        "cost": "$150,000/year",
                        "expected_result": "+30 candidates/quarter (3x acceleration)",
                        "timeline": "2 weeks (hire)",
                        "requires_approval_from": "VP_ENGINEERING"
                    },
                    {
                        "option": "ACCEPT_TIMELINE_DELAY",
                        "cost": "$0",
                        "expected_result": "Extended timeline, push delivery",
                        "timeline": "Flexible",
                        "requires_approval_from": "PARTNER"
                    }
                ],
                "escalation_node": "VP_ENGINEERING",  # Who should this escalate to?
                "recommendation": f"BEHIND target by {target - value} candidates. "
                                  f"Recommend immediate +$50K budget increase to acceleration recruitment.",
                "forecast_timestamp": datetime.utcnow().isoformat()
            }

            return forecast

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Recruitment forecasting failed: {e}", exc_info=True)
            raise

    @staticmethod
    def forecast_resource_needs(
        db: Session,
        phalanx: str = "resource_management"
    ) -> Dict[str, Any]:
        """
        Monitor resource utilization and forecast headcount needs
        """
        try:
            # Get current KPIs
            utilization_kpi = KPIService.calculate_kpi(db, phalanx, "resource_utilization", "weekly")
            demand_kpi = KPIService.calculate_kpi(db, phalanx, "demand_fulfillment", "weekly")

            forecast = {
                "forecast_id": str(uuid4()),
                "phalanx": phalanx,
                "current_state": {
                    "utilization_percent": utilization_kpi.get("value", 0),
                    "demand_fulfillment_percent": demand_kpi.get("value", 0)
                },
                "gap_analysis": {
                    "excess_utilization": utilization_kpi.get("value", 85) - 85,  # Above target
                    "unfulfilled_demand_percent": 100 - demand_kpi.get("value", 90),
                    "status": "UNDERSTAFFED" if demand_kpi.get("value", 90) < 85 else "HEALTHY"
                },
                "resource_options": [
                    {
                        "option": "INCREASE_HEADCOUNT",
                        "cost": "$2M/year for 10 FTE",
                        "expected_result": "Reduce utilization to 80%, improve demand fulfillment to 95%",
                        "timeline": "90 days (recruiting)",
                        "requires_approval_from": "PARTNER"
                    },
                    {
                        "option": "REDUCE_NEW_DEMAND",
                        "cost": "$0",
                        "expected_result": "Preserve team health, reduce scope",
                        "timeline": "Immediate",
                        "requires_approval_from": "PARTNER"
                    },
                    {
                        "option": "INCREASE_UTILIZATION_TARGET",
                        "cost": "$0 (but reduces team health)",
                        "expected_result": "Burnout risk increases",
                        "timeline": "Immediate",
                        "requires_approval_from": "BOARD"
                    }
                ],
                "escalation_node": "PARTNER",
                "recommendation": "Team at 95% utilization. Sustainable only with headcount increase.",
                "forecast_timestamp": datetime.utcnow().isoformat()
            }

            return forecast

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Resource forecasting failed: {e}", exc_info=True)
            raise

    @staticmethod
    def forecast_revenue_needs(
        db: Session,
        phalanx: str = "acquisition"
    ) -> Dict[str, Any]:
        """
        Forecast revenue needs based on company targets and burn rate

        NOTE: Acquisition is PROACTIVE (always hunting), not KPI-reactive
        But this forecasts WHAT revenue is needed
        """
        try:
            forecast = {
                "forecast_id": str(uuid4()),
                "phalanx": phalanx,
                "current_state": {
                    "quarterly_revenue_target": 4_000_000,
                    "revenue_to_date": 2_100_000,
                    "burn_rate": 1_200_000  # $/month operational cost
                },
                "gap_analysis": {
                    "revenue_gap": 4_000_000 - 2_100_000,  # 47.5% shortfall
                    "months_of_runway": 2_100_000 / 1_200_000,  # 1.75 months
                    "status": "CRITICAL"
                },
                "revenue_options": [
                    {
                        "option": "LAND_5_FORTUNE500",
                        "value": "$500K × 5 = $2.5M",
                        "probability": "45%",
                        "timeline": "60 days",
                        "requires_approval_from": "CRO"
                    },
                    {
                        "option": "EXPAND_EXISTING_CLIENTS",
                        "value": "$800K (land-and-expand average)",
                        "probability": "70%",
                        "timeline": "30 days",
                        "requires_approval_from": "ACCOUNT_MANAGER"
                    },
                    {
                        "option": "RAISE_PRICING",
                        "value": "+15% margin = $315K additional Q revenue",
                        "probability": "60%",
                        "timeline": "Immediate (for new contracts)",
                        "requires_approval_from": "CFO_AND_CRO"
                    }
                ],
                "escalation_node": "CRO",
                "recommendation": "CRITICAL: $1.9M gap with 1.75 months runway. "
                                  "Recommend simultaneous: land 2 Fortune 500 + aggressive land-and-expand + 10% price increase.",
                "forecast_timestamp": datetime.utcnow().isoformat()
            }

            return forecast

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Revenue forecasting failed: {e}", exc_info=True)
            raise

    @staticmethod
    def validate_decision_against_policy(
        db: Session,
        decision: Dict[str, Any],
        decision_maker_id: str
    ) -> Dict[str, Any]:
        """
        When a human makes a decision, validate it against system policies
        If it violates a policy, REJECT or WARN

        Example:
          CFO decides: "Approve Rust proposal at 25% margin"
          System checks: Policy = "MARGIN_FLOOR: 30%"
          Result: REJECTED - "Violates margin floor policy"
        """
        try:
            decision_type = decision.get("type")  # "APPROVE_PROPOSAL", "HIRE", "SET_TIMELINE"
            decision_params = decision.get("parameters", {})

            violations = []

            # Check relevant policies based on decision type
            if decision_type == "APPROVE_PROPOSAL":
                margin = decision_params.get("margin_percent")
                skill = decision_params.get("skill")

                # Example: Finance has "MARGIN_FLOOR: 30%" policy
                if margin and margin < 30:
                    violations.append({
                        "policy": "MARGIN_FLOOR",
                        "policy_value": "30%",
                        "decision_value": f"{margin}%",
                        "severity": "CRITICAL",
                        "rule": "Cannot approve proposals below 30% margin floor"
                    })

            elif decision_type == "ADJUST_TIMELINE":
                delay_days = decision_params.get("delay_days")

                # Example: Delivery has "MAX_DELAY: 14_DAYS" policy
                if delay_days and delay_days > 14:
                    violations.append({
                        "policy": "MAX_DELAY",
                        "policy_value": "14 days",
                        "decision_value": f"{delay_days} days",
                        "severity": "HIGH",
                        "rule": "Cannot delay project more than 14 days without board approval"
                    })

            # Return decision validation
            if violations:
                return {
                    "decision_id": str(uuid4()),
                    "validation_status": "POLICY_VIOLATION",
                    "severity": max(v["severity"] for v in violations),
                    "violations": violations,
                    "recommendation": self._generate_violation_response(decision_maker_id, violations),
                    "allow_override": True,
                    "requires_override_justification": True
                }
            else:
                return {
                    "decision_id": str(uuid4()),
                    "validation_status": "APPROVED",
                    "violations": [],
                    "recommendation": "Decision approved - no policy violations"
                }

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Decision validation failed: {e}", exc_info=True)
            raise

    @staticmethod
    def _generate_violation_response(decision_maker_id: str, violations: List[Dict]) -> str:
        """Generate autonomous rejection/warning message"""
        if len(violations) == 1:
            v = violations[0]
            if v["severity"] == "CRITICAL":
                return (f"❌ DECISION REJECTED\n"
                       f"Policy Violation: {v['policy']}\n"
                       f"Your decision: {v['decision_value']} < Required: {v['policy_value']}\n"
                       f"Rule: {v['rule']}\n"
                       f"Authority required: {v['severity']}")
            else:
                return (f"⚠️  DECISION WARNING\n"
                       f"Policy Violation: {v['policy']}\n"
                       f"Your decision: {v['decision_value']} > Guideline: {v['policy_value']}\n"
                       f"Would you like to override with Board justification?")
        else:
            return (f"❌ DECISION REJECTED - {len(violations)} policy violations\n" +
                   "\n".join(f"- {v['policy']}: {v['rule']}" for v in violations))

    @staticmethod
    def generate_autonomous_alert_to_human(
        db: Session,
        alert_type: str,  # "KPI_FALLEN", "DECISION_VIOLATES_POLICY", "FORECAST_NEED", "ESCALATION_REQUIRED"
        content: Dict[str, Any],
        escalate_to_node_id: str
    ) -> Dict[str, Any]:
        """
        System autonomously generates alert/message to human informing them of action
        This is the feedback loop: System → Human telling them they're wrong

        Example:
          System: "CFO approved margin below floor. This violates profitability guardrail.
                   We've blocked the proposal. Call me to discuss."
        """
        try:
            alert_id = str(uuid4())

            alert_templates = {
                "KPI_FALLEN": {
                    "subject": f"🚨 ALERT: {content['phalanx'].upper()} KPI fallen below threshold",
                    "body": f"""
Dear Manager,

Your {content['phalanx']} phalanx KPI has fallen below acceptable thresholds:

{content['kpi_name']}: {content['current_value']}/{content['target']} ({content['achievement_percent']}%)
Status: {content['status']}

Forecast shows you need:
{chr(10).join(f"• {opt['option']}: {opt['cost']} → {opt['expected_result']}" for opt in content['options'][:2])}

The system has NOT yet taken action (we're informing you first).
Please decide within 24 hours or we'll escalate to your manager.

Options:
A) Approve resource increase
B) Accept timeline delay
C) Adjust policy threshold (requires justification)

Regards,
Autonomous Forecasting System
"""
                },
                "DECISION_VIOLATES_POLICY": {
                    "subject": "⚠️  Your decision violates a system constraint",
                    "body": f"""
Your recent decision violates a system constraint:

Decision: {content['decision_type']}
Constraint: {content['policy_name']} = {content['policy_value']}
Your value: {content['decision_value']}

This decision has been BLOCKED until you provide justification.

The constraint exists because: {content['policy_reason']}

Would you like to:
A) Adjust your decision to comply
B) Override the constraint with justification
C) Escalate to your manager for approval

Reply within 4 hours or this escalates automatically.

Regards,
Autonomous Governance System
"""
                }
            }

            alert_template = alert_templates.get(alert_type, {})

            alert = {
                "alert_id": alert_id,
                "alert_type": alert_type,
                "escalate_to_node_id": escalate_to_node_id,
                "subject": alert_template.get("subject", "System Alert"),
                "body": alert_template.get("body", ""),
                "requires_response": True,
                "response_deadline_hours": 4 if alert_type == "DECISION_VIOLATES_POLICY" else 24,
                "auto_escalate_on_no_response": True,
                "created_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Autonomous alert generated: {alert_id}, escalating to {escalate_to_node_id}")
            return alert

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Alert generation failed: {e}", exc_info=True)
            raise
