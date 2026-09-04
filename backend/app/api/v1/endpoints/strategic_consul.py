"""Strategic Consul API - Human-in-Loop Governance Interface
Allows executives to resolve escalated decisions from DoctorAgentDaemon
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger

router = APIRouter(prefix="/spartan/governance", tags=["strategic-consul"])

@router.post(
    "/delivery-escalation",
    dependencies=[Depends(require_resource_permission("delivery-escalation", "create"))]
)
def resolve_delivery_escalation(
    escalation_id: str,
    bu_head_decision: str,  # "ALLOCATE_RESOURCES", "ADJUST_TIMELINE", "ESCALATE_TO_PARTNER"
    decision_rationale: str,
    bu_head_email: str,
    project_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delivery Escalation - BU Head Resolution

    When a delivery agent fails, escalation chain is:
    Agent (strike 3) → BU Head → Partner → CEO

    BU Head can:
    - ALLOCATE_RESOURCES: Pull bench engineers, increase velocity
    - ADJUST_TIMELINE: Negotiate 2-week extension with client
    - ESCALATE_TO_PARTNER: This is beyond BU head authority

    If ESCALATE_TO_PARTNER, it routes to partner for account-level decision
    """
    try:
        allowed_decisions = [
            "ALLOCATE_RESOURCES",
            "ADJUST_TIMELINE",
            "ESCALATE_TO_PARTNER"
        ]

        if bu_head_decision not in allowed_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision. Must be one of: {', '.join(allowed_decisions)}"
            )

        if bu_head_decision == "ESCALATE_TO_PARTNER":
            # Route to partner for account-level decision
            resolution = {
                "escalation_id": escalation_id,
                "stage": "BU_HEAD_DECISION",
                "bu_head_decision": bu_head_decision,
                "bu_head_email": bu_head_email,
                "project_id": project_id,
                "decision_timestamp": logger.timestamp() if hasattr(logger, 'timestamp') else None,
                "next_escalation_to": "PARTNER",
                "next_escalation_endpoint": "/spartan/governance/partner-escalation",
                "escalation_status": "ESCALATED_TO_PARTNER",
                "audit_record": {
                    "stage": "BU_HEAD",
                    "decision": bu_head_decision,
                    "rationale": decision_rationale,
                    "decided_by": bu_head_email
                }
            }
        else:
            # Execute BU Head decision locally
            resolution = {
                "escalation_id": escalation_id,
                "stage": "BU_HEAD_DECISION",
                "bu_head_decision": bu_head_decision,
                "bu_head_email": bu_head_email,
                "project_id": project_id,
                "decision_timestamp": logger.timestamp() if hasattr(logger, 'timestamp') else None,
                "execution_plan": _build_delivery_execution_plan(bu_head_decision),
                "pipeline_frozen": False,
                "pipeline_status": "UNFROZEN_AND_EXECUTING",
                "escalation_status": "RESOLVED_AT_BU_HEAD",
                "audit_record": {
                    "stage": "BU_HEAD",
                    "decision": bu_head_decision,
                    "rationale": decision_rationale,
                    "decided_by": bu_head_email
                }
            }

        logger.info(f"BU Head decision: escalation={escalation_id}, decision={bu_head_decision}")
        return {"data": resolution}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"BU Head escalation resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/partner-escalation",
    dependencies=[Depends(require_resource_permission("partner-escalation", "create"))]
)
def resolve_partner_escalation(
    escalation_id: str,
    bu_head_decision: str,  # What the BU Head tried
    partner_decision: str,  # "NEGOTIATE_EXTENSION", "OFFER_DISCOUNT", "ACCEPT_LOSS", "ESCALATE_TO_CEO"
    decision_rationale: str,
    partner_email: str,
    project_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Partner-Level Escalation - Account Retention Decision

    Partner can:
    - NEGOTIATE_EXTENSION: Client agrees to 2-3 week timeline shift
    - OFFER_DISCOUNT: Recover margin by offering client 10% discount + retention package
    - ACCEPT_LOSS: Accept the failure as sunk cost
    - ESCALATE_TO_CEO: Existential threat to account/company
    """
    try:
        allowed_decisions = [
            "NEGOTIATE_EXTENSION",
            "OFFER_DISCOUNT",
            "ACCEPT_LOSS",
            "ESCALATE_TO_CEO"
        ]

        if partner_decision not in allowed_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision. Must be one of: {', '.join(allowed_decisions)}"
            )

        resolution = {
            "escalation_id": escalation_id,
            "stage": "PARTNER_DECISION",
            "bu_head_decision": bu_head_decision,
            "partner_decision": partner_decision,
            "partner_email": partner_email,
            "project_id": project_id,
            "decision_timestamp": logger.timestamp() if hasattr(logger, 'timestamp') else None,
            "execution_plan": _build_partner_execution_plan(partner_decision),
            "pipeline_frozen": partner_decision != "ESCALATE_TO_CEO",
            "escalation_status": "RESOLVED_AT_PARTNER" if partner_decision != "ESCALATE_TO_CEO" else "ESCALATED_TO_CEO",
            "audit_record": {
                "stage": "PARTNER",
                "bu_head_tried": bu_head_decision,
                "partner_decided": partner_decision,
                "rationale": decision_rationale,
                "decided_by": partner_email
            }
        }

        logger.info(f"Partner decision: escalation={escalation_id}, decision={partner_decision}")
        return {"data": resolution}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Partner escalation resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/consul-resolve",
    dependencies=[Depends(require_resource_permission("consul-resolve", "create"))]
)
def resolve_escalation(
    escalation_id: str,
    strategic_decision: str,  # "RETRY_WITH_RESOURCES", "REDIRECT_TO_BACKUP", "ACCEPT_LOSS", "ADJUST_POLICY"
    decision_rationale: str,
    decision_maker: str,  # Email of executive making decision
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Strategic Consul Resolution Endpoint

    Executives use this to resolve DoctorAgentDaemon escalations.
    Decisions feed directly back into SLM processors to unfreeze pipelines.

    Args:
        escalation_id: ID from DoctorAgentDaemon critical isolation
        strategic_decision: One of the allowed resolution strategies
        decision_rationale: Why this decision (for audit trail)
        decision_maker: Email of executive resolving

    Returns:
        Execution plan that unfreezes the pipeline
    """
    try:
        allowed_decisions = [
            "RETRY_WITH_RESOURCES",
            "REDIRECT_TO_BACKUP",
            "ACCEPT_LOSS_AND_MOVE_ON",
            "ADJUST_POLICY",
            "ESCALATE_TO_CEO"
        ]

        if strategic_decision not in allowed_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision. Must be one of: {', '.join(allowed_decisions)}"
            )

        # Unfreeze the pipeline
        resolution_result = {
            "escalation_id": escalation_id,
            "strategic_decision": strategic_decision,
            "decision_maker": decision_maker,
            "decision_timestamp": logger.timestamp() if hasattr(logger, 'timestamp') else None,
            "execution_plan": _build_execution_plan(strategic_decision),
            "pipeline_frozen": False,
            "pipeline_status": "UNFROZEN_AND_EXECUTING",
            "audit_trail_record": {
                "decision": strategic_decision,
                "rationale": decision_rationale,
                "decided_by": decision_maker
            }
        }

        logger.info(f"Strategic decision resolved: escalation={escalation_id}, decision={strategic_decision}")
        return {"data": resolution_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Consul resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/escalations/pending",
    dependencies=[Depends(require_resource_permission("escalation", "view"))]
)
def list_pending_escalations(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all pending escalations awaiting strategic decisions
    Dashboard shows these to executives
    """
    try:
        # In production, query from escalation ledger
        pending_escalations = [
            {
                "escalation_id": "esc-001",
                "agent_id": "thunder-001",
                "phalanx": "recruitment",
                "failure_type": "CANDIDATE_SOURCING_STALLED",
                "urgency": "CRITICAL",
                "escalation_reason": "Thunder failed to source 50 candidates for DEMAND_SIGNED_LIVE",
                "timestamp": "2026-08-27T14:30:00Z",
                "awaiting_decision_from": ["VP_Engineering", "CTO"]
            },
            {
                "escalation_id": "esc-002",
                "agent_id": "invoice-manager-001",
                "phalanx": "finance",
                "failure_type": "MARGIN_VIOLATION",
                "urgency": "HIGH",
                "escalation_reason": "Margin fallen below 30% floor for Rust consultants",
                "timestamp": "2026-08-27T13:45:00Z",
                "awaiting_decision_from": ["CFO"]
            }
        ]

        return {
            "data": {
                "pending_count": len(pending_escalations),
                "escalations": pending_escalations
            }
        }

    except Exception as e:
        logger.error(f"Failed to list escalations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/formation/constraints",
    dependencies=[Depends(require_resource_permission("formation", "view"))]
)
def get_active_constraints(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all active constraint tokens in the system
    Shows margin guardrails, policy blocks, etc.
    """
    try:
        active_constraints = [
            {
                "constraint_id": "cst-001",
                "constraint_type": "MARGIN_FLOOR",
                "enforcing_phalanx": "finance",
                "affected_phalanx": "acquisition",
                "rule": "Rust consultants CANNOT be proposed below 35% margin",
                "expires_at": "2026-09-27T00:00:00Z",
                "reason": "Margin fell to 28% - protecting profitability"
            },
            {
                "constraint_id": "cst-002",
                "constraint_type": "CAPACITY_BLOCK",
                "enforcing_phalanx": "resource_management",
                "affected_phalanx": "acquisition",
                "rule": "Cannot accept new contracts requiring >80% utilization",
                "expires_at": "2026-12-31T00:00:00Z",
                "reason": "Current utilization at 95% - protecting team health"
            }
        ]

        return {
            "data": {
                "active_constraints_count": len(active_constraints),
                "constraints": active_constraints
            }
        }

    except Exception as e:
        logger.error(f"Failed to get constraints: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _build_execution_plan(decision: str) -> Dict[str, Any]:
    """Build execution plan based on strategic decision"""
    plans = {
        "RETRY_WITH_RESOURCES": {
            "action": "ALLOCATE_RESOURCES",
            "sub_actions": [
                "Pull 2 engineers from bench",
                "Increase Thunder search crawl by 500%",
                "Retry failing operation with fresh resources"
            ],
            "expected_timeline": "24 hours"
        },
        "REDIRECT_TO_BACKUP": {
            "action": "ACTIVATE_BACKUP_AGENT",
            "sub_actions": [
                "Activate backup system/process",
                "Transfer workload from failed agent",
                "Notify stakeholders of redirect"
            ],
            "expected_timeline": "Immediate"
        },
        "ACCEPT_LOSS_AND_MOVE_ON": {
            "action": "GRACEFUL_DEGRADATION",
            "sub_actions": [
                "Log incident for root-cause analysis",
                "Adjust KPIs to reflect accepted loss",
                "Resume pipeline operations"
            ],
            "expected_timeline": "1 hour"
        },
        "ADJUST_POLICY": {
            "action": "UPDATE_SYSTEM_POLICY",
            "sub_actions": [
                "Review failing agent's thresholds",
                "Adjust parameters for future resilience",
                "Document policy change in audit log"
            ],
            "expected_timeline": "4 hours"
        },
        "ESCALATE_TO_CEO": {
            "action": "BOARD_LEVEL_DECISION",
            "sub_actions": [
                "Escalate to C-suite",
                "Convene emergency strategy meeting",
                "Issue executive directive"
            ],
            "expected_timeline": "Business day"
        }
    }

    return plans.get(decision, {"action": "UNKNOWN", "sub_actions": []})

def _build_delivery_execution_plan(decision: str) -> Dict[str, Any]:
    """Build execution plan for BU Head delivery decisions"""
    plans = {
        "ALLOCATE_RESOURCES": {
            "action": "EMERGENCY_STAFFING",
            "sub_actions": [
                "Activate emergency bench reserve (2 senior engineers)",
                "Brief new engineers on project scope in 4 hours",
                "Increase daily standup frequency to 2x",
                "Implement daily progress tracking dashboard"
            ],
            "expected_recovery": "48-72 hours"
        },
        "ADJUST_TIMELINE": {
            "action": "CLIENT_NEGOTIATION",
            "sub_actions": [
                "Schedule urgent call with client stakeholder",
                "Propose 2-week timeline extension with risk mitigation plan",
                "Offer weekly executive briefings for transparency",
                "Ensure NPS impact is minimal"
            ],
            "expected_resolution": "24 hours"
        }
    }

    return plans.get(decision, {"action": "UNKNOWN", "sub_actions": []})

def _build_partner_execution_plan(decision: str) -> Dict[str, Any]:
    """Build execution plan for Partner account-level decisions"""
    plans = {
        "NEGOTIATE_EXTENSION": {
            "action": "ACCOUNT_RETENTION",
            "sub_actions": [
                "Partner meets with client sponsor + stakeholders",
                "Present recovery plan (scope + timeline)",
                "Secure written extension agreement",
                "Lock in renewal discussion for next phase"
            ],
            "expected_timeline": "48 hours to secure",
            "revenue_impact": "No loss"
        },
        "OFFER_DISCOUNT": {
            "action": "MARGIN_RECOVERY",
            "sub_actions": [
                "Propose 10% discount on current phase",
                "Bundle in free support retainer for 6 months",
                "Lock in 3-year managed services renewal",
                "Calculate lifetime value recovery"
            ],
            "expected_timeline": "72 hours to close",
            "revenue_impact": "Current phase -10%, renewals +50% LTV"
        },
        "ACCEPT_LOSS": {
            "action": "SUNK_COST",
            "sub_actions": [
                "Document post-mortem for root cause",
                "Plan prevention strategies for future projects",
                "Adjust account forecast",
                "Monitor relationship health closely"
            ],
            "expected_timeline": "Immediate acceptance",
            "revenue_impact": "Write off current phase, focus on retention"
        }
    }

    return plans.get(decision, {"action": "UNKNOWN", "sub_actions": []})
