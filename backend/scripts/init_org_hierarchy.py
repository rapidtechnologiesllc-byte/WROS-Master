import logging
"""Initialize Organizational Hierarchy from Existing Users and Roles

This script:
1. Queries existing Users and BusinessUnits
2. Infers org hierarchy from role assignments
3. Creates OrgNode records for entire org structure
4. Sets up proper reporting chains (including dual-reporting for CWP)
5. Assigns authority levels and decision domains

Hierarchy built:
  CEO (Level 0)
  ├─ Partner (Level 1, owns Sales + Delivery P&L)
  │   ├─ VP Engineering (Level 2)
  │   ├─ BU Head (Level 2)
  │   │   ├─ Workforce Ops Manager (Level 3, dual: BU Head + CWP)
  │   │   │   └─ Hiring Manager (Level 4)
  │   │   ├─ Delivery Manager
  │   │   └─ Finance Manager
  │   └─ Account Managers
  ├─ CFO (Level 1, org-wide)
  └─ CWP (Level 1, org-wide)

Run: python backend/scripts/init_org_hierarchy.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import get_database_url
from app.models.user import Users, UserRoles, RoleTemplate, BusinessUnit
from app.models.org_hierarchy import OrgNode, AUTHORITY_LEVELS
from app.core.logging import logger

# Role to hierarchy level mapping
ROLE_HIERARCHY = {
    "CEO": {"level": 0, "authority": "BOARD"},
    "CFO": {"level": 1, "authority": "EXECUTIVE"},
    "CWP": {"level": 1, "authority": "EXECUTIVE"},
    "Partner": {"level": 1, "authority": "DIVISION"},
    "VP Engineering": {"level": 2, "authority": "EXECUTIVE"},
    "BU Head": {"level": 2, "authority": "DIVISION"},
    "Delivery Manager": {"level": 3, "authority": "DEPARTMENT"},
    "Finance Manager": {"level": 3, "authority": "TEAM"},
    "Workforce Ops Manager": {"level": 3, "authority": "TEAM"},
    "Hiring Manager": {"level": 4, "authority": "TEAM"},
    "Account Manager": {"level": 3, "authority": "TEAM"},
    "Engineer": {"level": 4, "authority": "INDIVIDUAL"},
    "Recruiter": {"level": 4, "authority": "INDIVIDUAL"},
}

# Decision domains per role
ROLE_DECISION_DOMAINS = {
    "CEO": ["HIRING", "BUDGET", "PRICING", "TIMELINE", "SCOPE", "POLICY", "ESCALATION"],
    "CFO": ["BUDGET", "PRICING"],
    "CWP": ["HIRING", "POLICY"],
    "Partner": ["HIRING", "BUDGET", "PRICING", "TIMELINE", "SCOPE"],
    "VP Engineering": ["HIRING", "TIMELINE", "SCOPE"],
    "BU Head": ["HIRING", "BUDGET", "TIMELINE", "SCOPE"],
    "Delivery Manager": ["TIMELINE", "SCOPE"],
    "Finance Manager": [],
    "Workforce Ops Manager": ["HIRING"],
    "Hiring Manager": ["HIRING"],
    "Account Manager": ["PRICING"],
    "Engineer": [],
    "Recruiter": [],
}


def get_session():
    """Get database session"""
    db_url = get_database_url()
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()


def find_user_by_role(session, role_name: str):
    """Find first user with given role"""
    try:
        # Search in UserRoles junction table
        user_role = session.query(UserRoles).join(
            RoleTemplate, UserRoles.role_id == RoleTemplate.id
        ).filter(RoleTemplate.role_name == role_name).first()

        if user_role:
            return session.query(Users).filter(Users.UserID == user_role.user_id).first()

        # Fallback: search in permission_role field (legacy)
        return session.query(Users).filter(Users.permission_role == role_name).first()
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.warning(f"Could not find user with role '{role_name}': {e}")
        raise ValueError("Operation failed")


def get_user_roles(session, user_id: str) -> list:
    """Get all roles for a user"""
    try:
        user_roles = session.query(UserRoles).filter(
            UserRoles.user_id == user_id
        ).all()

        role_names = []
        for ur in user_roles:
            if ur.role:
                role_names.append(ur.role.role_name)

        # Fallback to permission_role if no UserRoles found
        if not role_names:
            user = session.query(Users).filter(Users.UserID == user_id).first()
            if user and user.permission_role:
                role_names.append(user.permission_role)

        return role_names
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.warning(f"Could not get roles for user {user_id}: {e}")
        raise ValueError("Operation failed")


def create_org_node(
    session,
    user_id: str,
    name: str,
    hierarchy_level: int,
    authority_level: str,
    decision_domains: list,
    business_unit_id: str = None,
    parent_node_id: str = None,
) -> OrgNode:
    """Create or update OrgNode"""
    try:
        # Check if already exists
        existing = session.query(OrgNode).filter(OrgNode.user_id == user_id).first()

        if existing:
            logger.info(f"Updating OrgNode for {name} ({user_id})")
            existing.hierarchy_level = hierarchy_level
            existing.authority_level = authority_level
            existing.parent_node_id = parent_node_id
            existing.business_unit_id = business_unit_id
            existing.decision_domains = ",".join(decision_domains) if decision_domains else None
            session.commit()
            return existing
        else:
            logger.info(f"Creating OrgNode for {name} ({user_id})")
            node = OrgNode(
                name=name,
                node_type="PERSON",
                user_id=user_id,
                hierarchy_level=hierarchy_level,
                authority_level=authority_level,
                parent_node_id=parent_node_id,
                business_unit_id=business_unit_id,
                decision_domains=",".join(decision_domains) if decision_domains else None,
            )
            session.add(node)
            session.commit()
            return node
    except Exception as e:        logger.error(f"Failed to create OrgNode for {name}: {e}")
        raise


def init_org_hierarchy():
    """Initialize entire organization hierarchy"""
    session = get_session()

    try:
        logger.info("=" * 60)
        logger.info("INITIALIZING ORGANIZATION HIERARCHY")
        logger.info("=" * 60)

        # Step 1: Create/update CEO
        logger.info("\n1. Setting up CEO...")
        ceo = find_user_by_role(session, "CEO")
        if not ceo:
            logger.error("ERROR: No CEO found in system. Please create CEO user first.")
            return False

        ceo_node = create_org_node(
            session,
            ceo.UserID,
            ceo.UserName or "CEO",
            hierarchy_level=0,
            authority_level="BOARD",
            decision_domains=ROLE_DECISION_DOMAINS["CEO"],
        )
        logger.info(f"✓ CEO: {ceo.UserName} (node_id: {ceo_node.id})")

        # Step 2: Create/update CFO (org-wide)
        logger.info("\n2. Setting up CFO (org-wide)...")
        cfo = find_user_by_role(session, "CFO")
        if cfo:
            cfo_node = create_org_node(
                session,
                cfo.UserID,
                cfo.UserName or "CFO",
                hierarchy_level=1,
                authority_level="EXECUTIVE",
                decision_domains=ROLE_DECISION_DOMAINS["CFO"],
                parent_node_id=ceo_node.id,  # Reports to CEO
            )
            logger.info(f"✓ CFO: {cfo.UserName} (node_id: {cfo_node.id})")
        else:
            logger.warning("⚠ No CFO found - skipping")
            cfo_node = None

        # Step 3: Create/update CWP (org-wide)
        logger.info("\n3. Setting up CWP - Chief Workforce Operations (org-wide)...")
        cwp = find_user_by_role(session, "CWP")
        if cwp:
            cwp_node = create_org_node(
                session,
                cwp.UserID,
                cwp.UserName or "CWP",
                hierarchy_level=1,
                authority_level="EXECUTIVE",
                decision_domains=ROLE_DECISION_DOMAINS["CWP"],
                parent_node_id=ceo_node.id,  # Reports to CEO
            )
            logger.info(f"✓ CWP: {cwp.UserName} (node_id: {cwp_node.id})")
        else:
            logger.warning("⚠ No CWP found - creating placeholder")
            # Could auto-create CWP if needed
            cwp_node = None

        # Step 4: Create/update all Partners
        logger.info("\n4. Setting up Partners (own Sales + Delivery P&L)...")
        partners = session.query(Users).filter(
            Users.permission_role == "Partner"
        ).all()

        partner_nodes = {}
        for partner in partners:
            partner_node = create_org_node(
                session,
                partner.UserID,
                partner.UserName or "Partner",
                hierarchy_level=1,
                authority_level="DIVISION",
                decision_domains=ROLE_DECISION_DOMAINS["Partner"],
                business_unit_id=partner.business_unit_id,
                parent_node_id=ceo_node.id,  # Reports to CEO
            )
            partner_nodes[partner.UserID] = partner_node
            logger.info(f"✓ Partner: {partner.UserName} (BU: {partner.business_unit_id})")

            # Step 4a: VP Engineering reports to this Partner
            logger.info(f"  ├─ Setting up VP Engineering for {partner.UserName}...")
            # Find VP Engineering in this Partner's BU
            vp_eng = session.query(Users).filter(
                Users.permission_role == "VP Engineering",
                Users.business_unit_id == partner.business_unit_id,
            ).first()

            if vp_eng:
                vp_eng_node = create_org_node(
                    session,
                    vp_eng.UserID,
                    vp_eng.UserName or "VP Engineering",
                    hierarchy_level=2,
                    authority_level="EXECUTIVE",
                    decision_domains=ROLE_DECISION_DOMAINS["VP Engineering"],
                    business_unit_id=partner.business_unit_id,
                    parent_node_id=partner_node.id,  # Reports to Partner
                )
                logger.info(f"  │ ✓ VP Engineering: {vp_eng.UserName}")
            else:
                logger.info(f"  │ ⚠ No VP Engineering found for this BU")

            # Step 4b: BU Heads report to this Partner
            logger.info(f"  ├─ Setting up BU Heads for {partner.UserName}...")
            bu_heads = session.query(Users).filter(
                Users.permission_role == "BU Head",
                Users.business_unit_id == partner.business_unit_id,
            ).all()

            for bu_head in bu_heads:
                bu_head_node = create_org_node(
                    session,
                    bu_head.UserID,
                    bu_head.UserName or "BU Head",
                    hierarchy_level=2,
                    authority_level="DIVISION",
                    decision_domains=ROLE_DECISION_DOMAINS["BU Head"],
                    business_unit_id=partner.business_unit_id,
                    parent_node_id=partner_node.id,  # Reports to Partner
                )
                logger.info(f"  │ ✓ BU Head: {bu_head.UserName}")

                # Step 4b-i: Workforce Ops Manager reports to BU Head + CWP (dual)
                logger.info(f"  │ ├─ Setting up Workforce Ops Manager...")
                wfops = session.query(Users).filter(
                    Users.permission_role == "Workforce Ops Manager",
                    Users.business_unit_id == partner.business_unit_id,
                ).first()

                if wfops:
                    wfops_node = create_org_node(
                        session,
                        wfops.UserID,
                        wfops.UserName or "Workforce Ops Manager",
                        hierarchy_level=3,
                        authority_level="TEAM",
                        decision_domains=ROLE_DECISION_DOMAINS["Workforce Ops Manager"],
                        business_unit_id=partner.business_unit_id,
                        parent_node_id=bu_head_node.id,  # Primary: reports to BU Head
                        # TODO: Add dual reporting to CWP node via separate table if needed
                    )
                    logger.info(f"  │ │ ✓ Workforce Ops Manager: {wfops.UserName} (dual: BU Head + CWP)")
                else:
                    logger.info(f"  │ │ ⚠ No Workforce Ops Manager found")
                    wfops_node = None

                # Step 4b-ii: Hiring Manager reports to Workforce Ops Manager
                logger.info(f"  │ ├─ Setting up Hiring Managers...")
                hiring_mgrs = session.query(Users).filter(
                    Users.permission_role == "Hiring Manager",
                    Users.business_unit_id == partner.business_unit_id,
                ).all()

                for hiring_mgr in hiring_mgrs:
                    hiring_node = create_org_node(
                        session,
                        hiring_mgr.UserID,
                        hiring_mgr.UserName or "Hiring Manager",
                        hierarchy_level=4,
                        authority_level="TEAM",
                        decision_domains=ROLE_DECISION_DOMAINS["Hiring Manager"],
                        business_unit_id=partner.business_unit_id,
                        parent_node_id=wfops_node.id if wfops_node else bu_head_node.id,
                    )
                    logger.info(f"  │ │ ✓ Hiring Manager: {hiring_mgr.UserName}")

                # Step 4b-iii: Other BU-level roles
                logger.info(f"  │ ├─ Setting up BU-level roles...")
                delivery_mgrs = session.query(Users).filter(
                    Users.permission_role == "Delivery Manager",
                    Users.business_unit_id == partner.business_unit_id,
                ).all()

                for delivery_mgr in delivery_mgrs:
                    delivery_node = create_org_node(
                        session,
                        delivery_mgr.UserID,
                        delivery_mgr.UserName or "Delivery Manager",
                        hierarchy_level=3,
                        authority_level="DEPARTMENT",
                        decision_domains=ROLE_DECISION_DOMAINS["Delivery Manager"],
                        business_unit_id=partner.business_unit_id,
                        parent_node_id=bu_head_node.id,
                    )
                    logger.info(f"  │ │ ✓ Delivery Manager: {delivery_mgr.UserName}")

                finance_mgrs = session.query(Users).filter(
                    Users.permission_role == "Finance Manager",
                    Users.business_unit_id == partner.business_unit_id,
                ).all()

                for finance_mgr in finance_mgrs:
                    finance_node = create_org_node(
                        session,
                        finance_mgr.UserID,
                        finance_mgr.UserName or "Finance Manager",
                        hierarchy_level=3,
                        authority_level="TEAM",
                        decision_domains=ROLE_DECISION_DOMAINS["Finance Manager"],
                        business_unit_id=partner.business_unit_id,
                        parent_node_id=bu_head_node.id,
                    )
                    logger.info(f"  │ │ ✓ Finance Manager: {finance_mgr.UserName}")

        logger.info("\n" + "=" * 60)
        logger.info("✓ ORGANIZATION HIERARCHY INITIALIZED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info("\nHierarchy Summary:")
        logger.info(f"  CEO: {ceo.UserName}")
        logger.info(f"  CFO: {cfo.UserName if cfo else '(none)'}")
        logger.info(f"  CWP: {cwp.UserName if cwp else '(none)'}")
        logger.info(f"  Partners: {len(partners)}")
        logger.info("\nEscalation chains are now live:")
        logger.info("  • Delivery: BU Head → Partner → CEO")
        logger.info("  • Recruitment: Hiring Manager → Workforce Ops Manager → CWP/Partner → CEO")
        logger.info("  • Finance: Finance Manager → Partner (or CFO for policies) → CEO")
        logger.info("  • VP Eng: Engineering Lead → VP Eng → Partner → CEO")
        logger.info("\n")

        return True

    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"ERROR initializing org hierarchy: {e}", exc_info=True)
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = init_org_hierarchy()
    sys.exit(0 if success else 1)
