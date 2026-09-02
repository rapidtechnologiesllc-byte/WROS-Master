"""DoctorAgentDaemon: Active Governance Layer
Enforces The Contract through 3-strike escalation, upstream balancing loops, and strategic consul interface
"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger

class DoctorAgentDaemon:
    """Active health enforcement daemon with 3-strike escalation logic"""

    # Strike definitions
    STRIKE_LEVELS = {
        1: {"action": "AUTO_HEAL", "description": "Automatic recovery attempt"},
        2: {"action": "ADJACENT_SHIELD", "description": "Call adjacent phalanx for support"},
        3: {"action": "CRITICAL_ISOLATION", "description": "Freeze pipeline, escalate to Strategic Consul"}
    }

    @staticmethod
    def process_operation_failure(
        db: Session,
        operation_id: str,
        agent_id: str,
        error_type: str,
        error_message: str,
        phalanx: str
    ) -> Dict[str, Any]:
        """
        Detect operation failure and enforce 3-strike escalation logic
        This is the core governance engine
        """
        try:
            # Get current strike count for this agent
            strike_count = DoctorAgentDaemon._get_strike_count(db, agent_id)
            strike_count += 1

            escalation_result = None

            if strike_count == 1:
                # STRIKE 1: AUTO-HEAL
                escalation_result = DoctorAgentDaemon._strike_one_auto_heal(
                    db, operation_id, agent_id, error_type
                )

            elif strike_count == 2:
                # STRIKE 2: ADJACENT SHIELD
                escalation_result = DoctorAgentDaemon._strike_two_adjacent_shield(
                    db, operation_id, agent_id, phalanx
                )

            elif strike_count >= 3:
                # STRIKE 3: CRITICAL ISOLATION
                escalation_result = DoctorAgentDaemon._strike_three_critical_isolation(
                    db, operation_id, agent_id, phalanx, error_message
                )

            # Log the failure
            DoctorAgentDaemon._log_agent_strike(
                db, agent_id, strike_count, error_type, escalation_result
            )

            return {
                "operation_id": operation_id,
                "agent_id": agent_id,
                "strike_count": strike_count,
                "action": STRIKE_LEVELS[min(strike_count, 3)]["action"],
                "escalation_result": escalation_result,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Doctor agent processing failed: {e}", exc_info=True)
            raise ValueError(f"Doctor agent failed: {str(e)}")

    @staticmethod
    def _strike_one_auto_heal(
        db: Session,
        operation_id: str,
        agent_id: str,
        error_type: str
    ) -> Dict[str, Any]:
        """
        STRIKE 1: Automatic Recovery
        Rollback to template, retry operation
        """
        try:
            # Template-based rollback
            rollback_result = {
                "action": "AUTO_HEAL",
                "rollback_target": f"template-{agent_id}",
                "retry_attempt": 1,
                "retry_strategy": "EXPONENTIAL_BACKOFF",
                "retry_delays": [2, 5, 10],  # seconds
                "status": "RECOVERY_INITIATED"
            }

            logger.info(f"Strike 1 - Auto heal initiated: {operation_id}")
            return rollback_result

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Auto-heal failed: {e}")
            return {"action": "AUTO_HEAL", "status": "FAILED", "error": str(e)}

    @staticmethod
    def _strike_two_adjacent_shield(
        db: Session,
        operation_id: str,
        agent_id: str,
        failing_phalanx: str
    ) -> Dict[str, Any]:
        """
        STRIKE 2: Adjacent Phalanx Shielding
        Command adjacent phalanx to buffer the failure
        Example: If Recruitment is failing, ask Resource Management to hold the line
        """
        try:
            # Phalanx adjacency map (who protects whom)
            shield_map = {
                "recruitment": "resource_management",  # Resource team can provide interim staffing
                "resource_management": "finance",  # Finance can adjust delivery terms
                "finance": "recruitment",  # Recruitment can adjust scope
                "delivery": "finance",  # Finance can provide budget relief
                "acquisition": "delivery"  # Delivery can support account management
            }

            adjacent_phalanx = shield_map.get(failing_phalanx)

            shield_result = {
                "action": "ADJACENT_SHIELD",
                "failing_phalanx": failing_phalanx,
                "supporting_phalanx": adjacent_phalanx,
                "buffer_payload": {
                    "operation_id": operation_id,
                    "original_agent_id": agent_id,
                    "priority": "EMERGENCY_SUPPORT",
                    "buffering_action": f"SUPPORT_{failing_phalanx.upper()}"
                },
                "shield_status": "ACTIVATED",
                "shield_duration": "UNTIL_ORIGINAL_AGENT_RECOVERS"
            }

            logger.info(f"Strike 2 - Adjacent shield: {adjacent_phalanx} supporting {failing_phalanx}")
            return shield_result

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Adjacent shield activation failed: {e}")
            return {"action": "ADJACENT_SHIELD", "status": "FAILED", "error": str(e)}

    @staticmethod
    def _strike_three_critical_isolation(
        db: Session,
        operation_id: str,
        agent_id: str,
        phalanx: str,
        error_message: str,
        project_id: str = None,
        bu_head_id: str = None,
        partner_id: str = None
    ) -> Dict[str, Any]:
        """
        STRIKE 3: Critical Isolation & Escalation Chain
        Delivery Phalanx escalates through BU Head → Partner
        Other phalanxes escalate directly to Strategic Consul

        Escalation Hierarchy:
        - Delivery: Agent → BU Head → Partner → CEO
        - Other: Agent → Strategic Consul
        """
        try:
            is_delivery_escalation = phalanx == "delivery"

            if is_delivery_escalation:
                # Route through BU Head → Partner hierarchy
                escalation_ticket = {
                    "escalation_id": str(uuid4()),
                    "escalation_type": "CRITICAL_DELIVERY_FAILURE",
                    "escalation_chain": "BU_HEAD → PARTNER → CEO",
                    "agent_id": agent_id,
                    "phalanx": phalanx,
                    "project_id": project_id,
                    "operation_id": operation_id,
                    "error_message": error_message,
                    "pipeline_frozen": True,
                    "frozen_phalanx": phalanx,
                    "first_escalation_to": "BU_HEAD",
                    "bu_head_id": bu_head_id,
                    "second_escalation_to": "PARTNER",
                    "partner_id": partner_id,
                    "third_escalation_to": "CEO",
                    "pipeline_freeze_reason": f"Critical delivery failure: {agent_id} failed 3 times",
                    "escalation_endpoint": f"/spartan/governance/delivery-escalation",
                    "decisions_required_at_bu_head": [
                        f"Assess delivery impact on project {project_id}",
                        f"Decide: Emergency resource allocation? Timeline adjustment? Client notification?",
                        f"If unresolvable, escalate to Partner"
                    ],
                    "decisions_required_at_partner": [
                        f"Assess account-level impact",
                        f"Decide: Negotiate extension? Discount recovery? Client retention strategy?",
                        f"If unresolvable, escalate to CEO"
                    ],
                    "escalation_timestamp": datetime.utcnow().isoformat(),
                    "status": "AWAITING_BU_HEAD_DECISION"
                }
            else:
                # Direct escalation to Strategic Consul for non-delivery phalanxes
                escalation_ticket = {
                    "escalation_id": str(uuid4()),
                    "escalation_type": "CRITICAL_AGENT_FAILURE",
                    "escalation_chain": "STRATEGIC_CONSUL",
                    "agent_id": agent_id,
                    "phalanx": phalanx,
                    "operation_id": operation_id,
                    "error_message": error_message,
                    "pipeline_frozen": True,
                    "frozen_phalanx": phalanx,
                    "pipeline_freeze_reason": f"Agent {agent_id} in {phalanx} failed 3 times",
                    "escalation_endpoint": f"/spartan/governance/consul-resolve",
                    "strategic_decisions_required": [
                        f"Assess root cause of {agent_id} failure",
                        f"Decide: Retry with new resources? Redirect to backup? Accept loss?",
                        f"Adjust thresholds/policies for {phalanx}?"
                    ],
                    "escalation_timestamp": datetime.utcnow().isoformat(),
                    "status": "AWAITING_STRATEGIC_CONSUL_DECISION"
                }

            logger.critical(f"Strike 3 - Critical isolation: {escalation_ticket['escalation_id']}, chain={escalation_ticket['escalation_chain']}")
            return escalation_ticket

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Critical isolation failed: {e}")
            return {"action": "CRITICAL_ISOLATION", "status": "FAILED", "error": str(e)}

    @staticmethod
    def enforce_upstream_balancing_loop(
        db: Session,
        demanding_phalanx: str,
        unfulfilled_demand: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upstream Balancing Loop - Service enforces contract
        Example: If Demand Mgmt has unfulfilled vacancy → boost Recruitment

        The Contract:
        "If DemandManagementService logs an unfulfilled vacancy under DEMAND_SIGNED_LIVE,
         it must autonomously post a high-priority recruitment.candidate_intake message,
         forcing Thunder to increase crawling speed by 500%"
        """
        try:
            # Evaluate demand urgency
            if unfulfilled_demand.get("temporal_priority") == "DEMAND_SIGNED_LIVE":
                # CRITICAL: Force upstream recruitment to accelerate

                acceleration_command = {
                    "command_id": str(uuid4()),
                    "source_phalanx": demanding_phalanx,
                    "target_phalanx": "recruitment",
                    "command_type": "ACCELERATE_SEARCH",
                    "search_parameters": {
                        "skill": unfulfilled_demand.get("required_skill"),
                        "urgency": "CRITICAL",
                        "search_intensity_multiplier": 5.0  # Increase by 500%
                    },
                    "queue_topic": "recruitment.candidate_intake",
                    "queue_priority": "CRITICAL",
                    "message": f"DEMAND_SIGNED_LIVE: Need {unfulfilled_demand.get('required_skill')} resource within 48h",
                    "enforcement_status": "CONSTRAINT_ENFORCED"
                }

                logger.info(f"Upstream balancing: {demanding_phalanx} escalating to recruitment")
                return acceleration_command

            return {"status": "NO_BALANCING_REQUIRED"}

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Upstream balancing failed: {e}")
            raise

    @staticmethod
    def enforce_margin_guardrail(
        db: Session,
        phalanx: str,  # "finance"
        profit_margin_percent: float,
        skill_profile: str
    ) -> Dict[str, Any]:
        """
        Margin Guardrail Constraint Token
        If margins drop → block Acquisition from offering below margin floor

        The Contract:
        "If FinanceService flags a drop in profit margins for a specific skill profile,
         it must write a constraint token to the ledger that blocks AcquisitionService
         from offering proposals below that updated margin floor."
        """
        try:
            if profit_margin_percent < 30:  # Default margin floor
                # CRITICAL: Enforce margin guardrail

                constraint_token = {
                    "constraint_id": str(uuid4()),
                    "constraint_type": "MARGIN_FLOOR",
                    "enforcing_phalanx": "finance",
                    "enforcing_service": "FinanceService.enforce_margin_guardrail",
                    "affected_phalanx": "acquisition",
                    "skill_profile": skill_profile,
                    "margin_floor_percent": max(profit_margin_percent + 5, 30),  # Enforce with 5% buffer
                    "blocking_rule": f"AcquisitionService CANNOT propose {skill_profile} engagements below {max(profit_margin_percent + 5, 30)}% margin",
                    "constraint_active": True,
                    "expires_at": (datetime.utcnow() + __import__('datetime').timedelta(days=30)).isoformat()
                }

                logger.warning(f"Margin guardrail enforced: {skill_profile} must maintain {constraint_token['margin_floor_percent']}% margin")
                return constraint_token

            return {"status": "MARGIN_HEALTHY", "no_constraint_required": True}

        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Margin guardrail enforcement failed: {e}")
            raise

    @staticmethod
    def _get_strike_count(db: Session, agent_id: str) -> int:
        """Get current strike count for an agent (from audit log)"""
        # Would query from strike_count table in production
        return 0  # Placeholder

    @staticmethod
    def _log_agent_strike(
        db: Session,
        agent_id: str,
        strike_count: int,
        error_type: str,
        escalation_result: Dict[str, Any]
    ) -> None:
        """Log strike to audit trail"""
        logger.info(
            f"Agent strike logged: agent={agent_id}, strike={strike_count}, "
            f"error_type={error_type}, action={escalation_result.get('action', 'UNKNOWN')}"
        )
