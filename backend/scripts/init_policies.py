"""Initialize System Decision Policies

This script seeds core policies that the system enforces:
- MARGIN_FLOOR: Minimum margin for proposals
- UTILIZATION_CEILING: Maximum resource utilization target
- DELIVERY_SLA: Maximum delivery delay allowed
- REVENUE_FLOOR: Minimum price for contracts
- RECRUITMENT_PACE: Minimum sourcing rate targets

These policies are enforced by:
1. AutonomousForecastingService.validate_decision_against_policy()
2. DoctorAgentDaemon when failures occur
3. StrategicConsul escalations

Run: python backend/scripts/init_policies.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import get_database_url
from app.models.org_hierarchy import DecisionPolicy
from app.core.logging import logger


def get_session():
    """Get database session"""
    db_url = get_database_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


def create_policy(
    session,
    policy_name: str,
    policy_domain: str,
    phalanx: str,
    rule_type: str,
    rule_value: str,
    condition: str = None,
    can_override: bool = True,
    override_authority: str = None,
    override_justification_required: bool = True,
) -> DecisionPolicy:
    """Create or update a decision policy"""
    try:
        # Check if already exists
        existing = session.query(DecisionPolicy).filter(
            DecisionPolicy.policy_name == policy_name,
            DecisionPolicy.phalanx == phalanx,
        ).first()

        if existing:
            logger.info(f"Updating policy: {policy_name}")
            existing.rule_value = rule_value
            existing.condition = condition
            existing.can_override = can_override
            existing.override_authority = override_authority
            existing.override_justification_required = override_justification_required
            session.commit()
            return existing
        else:
            logger.info(f"Creating policy: {policy_name}")
            policy = DecisionPolicy(
                policy_name=policy_name,
                policy_domain=policy_domain,
                phalanx=phalanx,
                rule_type=rule_type,
                rule_value=rule_value,
                condition=condition,
                can_override=can_override,
                override_authority=override_authority,
                override_justification_required=override_justification_required,
                is_active=True,
            )
            session.add(policy)
            session.commit()
            return policy
    except Exception as e:
        logger.error(f"Failed to create policy {policy_name}: {e}")
        raise


def init_policies():
    """Initialize all system policies"""
    session = get_session()

    try:
        logger.info("=" * 60)
        logger.info("INITIALIZING SYSTEM POLICIES")
        logger.info("=" * 60)

        # FINANCE POLICIES
        logger.info("\n1. Finance Policies...")

        create_policy(
            session,
            policy_name="MARGIN_FLOOR",
            policy_domain="PRICING",
            phalanx="finance",
            rule_type="FLOOR",
            rule_value="30%",
            condition="All proposals must have minimum 30% margin",
            can_override=True,
            override_authority="CFO",
            override_justification_required=True,
        )
        logger.info("  ✓ MARGIN_FLOOR: Minimum 30% margin on all proposals")

        create_policy(
            session,
            policy_name="STRATEGIC_CLIENT_MARGIN",
            policy_domain="PRICING",
            phalanx="finance",
            rule_type="FLOOR",
            rule_value="20%",
            condition="Strategic Fortune 500 clients can have 20% minimum margin",
            can_override=True,
            override_authority="CFO",
            override_justification_required=True,
        )
        logger.info("  ✓ STRATEGIC_CLIENT_MARGIN: 20% minimum for Fortune 500")

        create_policy(
            session,
            policy_name="COST_PER_FTE",
            policy_domain="BUDGET",
            phalanx="finance",
            rule_type="CEILING",
            rule_value="$250,000",
            condition="Maximum annual cost per full-time employee",
            can_override=True,
            override_authority="CFO",
            override_justification_required=True,
        )
        logger.info("  ✓ COST_PER_FTE: Maximum $250K/year per employee")

        # RESOURCE MANAGEMENT POLICIES
        logger.info("\n2. Resource Management Policies...")

        create_policy(
            session,
            policy_name="UTILIZATION_CEILING",
            policy_domain="UTILIZATION",
            phalanx="resource_management",
            rule_type="CEILING",
            rule_value="85%",
            condition="Team utilization must not exceed 85% to maintain health",
            can_override=True,
            override_authority="PARTNER",
            override_justification_required=True,
        )
        logger.info("  ✓ UTILIZATION_CEILING: Maximum 85% utilization")

        create_policy(
            session,
            policy_name="DEMAND_FULFILLMENT",
            policy_domain="UTILIZATION",
            phalanx="resource_management",
            rule_type="FLOOR",
            rule_value="90%",
            condition="Demand fulfillment must be at least 90%",
            can_override=True,
            override_authority="PARTNER",
            override_justification_required=True,
        )
        logger.info("  ✓ DEMAND_FULFILLMENT: Minimum 90% fulfillment rate")

        # DELIVERY POLICIES
        logger.info("\n3. Delivery Policies...")

        create_policy(
            session,
            policy_name="MAX_DELIVERY_DELAY",
            policy_domain="TIMELINE",
            phalanx="delivery",
            rule_type="CEILING",
            rule_value="14 days",
            condition="Project delays cannot exceed 14 days without escalation",
            can_override=True,
            override_authority="PARTNER",
            override_justification_required=True,
        )
        logger.info("  ✓ MAX_DELIVERY_DELAY: 14-day maximum without escalation")

        create_policy(
            session,
            policy_name="SLA_BREACH_THRESHOLD",
            policy_domain="TIMELINE",
            phalanx="delivery",
            rule_type="CEILING",
            rule_value="5%",
            condition="SLA breaches must not exceed 5% of deliverables",
            can_override=True,
            override_authority="PARTNER",
            override_justification_required=True,
        )
        logger.info("  ✓ SLA_BREACH_THRESHOLD: Maximum 5% SLA breaches")

        # RECRUITMENT POLICIES
        logger.info("\n4. Recruitment Policies...")

        create_policy(
            session,
            policy_name="HIRING_PACE",
            policy_domain="HIRING",
            phalanx="recruitment",
            rule_type="FLOOR",
            rule_value="Proportional to demand",
            condition="Hiring pace must keep up with resource demand",
            can_override=True,
            override_authority="CWP",
            override_justification_required=True,
        )
        logger.info("  ✓ HIRING_PACE: Must keep up with demand")

        create_policy(
            session,
            policy_name="TIME_TO_HIRE",
            policy_domain="HIRING",
            phalanx="recruitment",
            rule_type="CEILING",
            rule_value="45 days",
            condition="Time from offer to start must not exceed 45 days",
            can_override=True,
            override_authority="CWP",
            override_justification_required=True,
        )
        logger.info("  ✓ TIME_TO_HIRE: Maximum 45 days from offer to start")

        create_policy(
            session,
            policy_name="OFFER_ACCEPTANCE_RATE",
            policy_domain="HIRING",
            phalanx="recruitment",
            rule_type="FLOOR",
            rule_value="75%",
            condition="Offer acceptance rate must be at least 75%",
            can_override=True,
            override_authority="CWP",
            override_justification_required=True,
        )
        logger.info("  ✓ OFFER_ACCEPTANCE_RATE: Minimum 75% acceptance")

        # ACQUISITION POLICIES
        logger.info("\n5. Acquisition Policies...")

        create_policy(
            session,
            policy_name="RUNWAY_MINIMUM",
            policy_domain="BUDGET",
            phalanx="acquisition",
            rule_type="FLOOR",
            rule_value="6 months",
            condition="Company must maintain 6+ months cash runway",
            can_override=False,  # Cannot override - existential
            override_authority="CEO",
            override_justification_required=True,
        )
        logger.info("  ✓ RUNWAY_MINIMUM: 6+ months cash required")

        create_policy(
            session,
            policy_name="QUARTERLY_REVENUE_TARGET",
            policy_domain="BUDGET",
            phalanx="acquisition",
            rule_type="FLOOR",
            rule_value="$4M/quarter",
            condition="Minimum quarterly revenue target",
            can_override=True,
            override_authority="CEO",
            override_justification_required=True,
        )
        logger.info("  ✓ QUARTERLY_REVENUE_TARGET: $4M/quarter minimum")

        create_policy(
            session,
            policy_name="NEW_CLIENT_PACE",
            policy_domain="HIRING",
            phalanx="acquisition",
            rule_type="FLOOR",
            rule_value="1 new client every 2 weeks",
            condition="Autonomous acquisition team must land 1 new client every 2 weeks",
            can_override=True,
            override_authority="CRO",
            override_justification_required=True,
        )
        logger.info("  ✓ NEW_CLIENT_PACE: 1 client/2 weeks")

        logger.info("\n" + "=" * 60)
        logger.info("✓ SYSTEM POLICIES INITIALIZED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info("\nPolicy Summary:")
        logger.info("  Finance: 3 policies (margin floor, cost/FTE, strategic clients)")
        logger.info("  Resources: 2 policies (utilization, demand fulfillment)")
        logger.info("  Delivery: 2 policies (max delay, SLA breach threshold)")
        logger.info("  Recruitment: 3 policies (hiring pace, time-to-hire, offer acceptance)")
        logger.info("  Acquisition: 3 policies (runway, revenue target, new client pace)")
        logger.info("\nAll policies are now enforced by:")
        logger.info("  • AutonomousForecastingService.validate_decision_against_policy()")
        logger.info("  • DoctorAgentDaemon escalations")
        logger.info("  • StrategicConsul decision validation")
        logger.info("\n")

        return True

    except Exception as e:
        logger.error(f"ERROR initializing policies: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = init_policies()
    sys.exit(0 if success else 1)
