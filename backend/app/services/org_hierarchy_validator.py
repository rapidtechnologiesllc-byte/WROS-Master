"""Organization Hierarchy Validator

Enforces reporting structure rules for the 17-level organizational hierarchy with specializations.

Hierarchy Levels (1-17):
- Level 1: Intern
- Level 2: Associate
- Level 3: Senior Associate
- Level 4: Consultant
- Level 5: Senior Consultant
- Level 6: Lead Consultant
- Level 7: Associate Manager
- Level 8: Manager
- Level 9: Senior Manager
- Level 10: Assistant Director
- Level 11: Director
- Level 12: Senior Director
- Level 13: Assistant Vice President (AVP)
- Level 14: Vice President (VP)
- Level 15: Senior Vice President (SVP)
- Level 16: Partner / C-Level
- Level 17: CEO

Specializations: Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis

Rules:
1. Cannot skip more than 2 levels (Intern → Associate/Senior Associate OK, but not Intern → Consultant)
2. Parent must be at higher level (lower hierarchy_level number)
3. Specializations must align (Dev reports to Dev leads/managers, not Recruitment managers)
4. Same business unit unless parent is org-wide (CFO, CWP)
5. No circular reporting chains
"""

import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.org_structure import OrgNode
from app.core.logging import logger

# Define the 17-level hierarchy with specialization rules
HIERARCHY_LEVELS = {
    1: "Intern",
    2: "Associate",
    3: "Senior Associate",
    4: "Consultant",
    5: "Senior Consultant",
    6: "Lead Consultant",
    7: "Associate Manager",
    8: "Manager",
    9: "Senior Manager",
    10: "Assistant Director",
    11: "Director",
    12: "Senior Director",
    13: "Assistant Vice President",
    14: "Vice President",
    15: "Senior Vice President",
    16: "Partner / C-Level",
    17: "CEO"
}

# Define valid specializations
SPECIALIZATIONS = [
    "Recruitment",
    "Development",
    "HR",
    "Finance",
    "Project Management",
    "QA",
    "Business Analysis",
    "General"  # For roles without specific specialization
]

# Define which levels can report to which levels (no more than 2 level gap)
# Example: Level 1 can report to 2, 3; Level 4 can report to 6, 7, 8
def get_valid_parent_levels(employee_level: int) -> list:
    """Get valid parent hierarchy levels for an employee at a given level"""
    if employee_level >= 17:
        return []  # CEO reports to nobody

    # Can report to: next level up, or up to 2 levels up
    valid_levels = []
    for i in range(employee_level + 1, min(employee_level + 3, 18)):
        valid_levels.append(i)
    return valid_levels


class OrgHierarchyValidator:
    """Validates organizational hierarchy with 17 levels and specialization enforcement"""

    @staticmethod
    def validate_reporting_relationship(
        session: Session,
        employee_hierarchy_level: int,
        employee_specialization: str,
        parent_node_id: Optional[str],
        business_unit_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a new employee's reporting relationship is valid

        Args:
            session: Database session
            employee_hierarchy_level: Hierarchy level (1-17) of the new employee
            employee_specialization: Specialization (Recruitment, Development, etc.)
            parent_node_id: UUID of who they report to
            business_unit_id: Their business unit

        Returns:
            (is_valid, error_message)
            - (True, None) if valid
            - (False, error_message) if invalid
        """
        try:
            # Validate hierarchy level
            if not isinstance(employee_hierarchy_level, int) or employee_hierarchy_level < 1 or employee_hierarchy_level > 17:
                return (False, f"Invalid hierarchy level: {employee_hierarchy_level}. Must be 1-17.")

            # Validate specialization
            if employee_specialization not in SPECIALIZATIONS:
                return (False, f"Unknown specialization: {employee_specialization}. Valid: {', '.join(SPECIALIZATIONS)}")

            # CEO doesn't report to anyone
            if employee_hierarchy_level == 17:
                if parent_node_id is not None:
                    return (False, "CEO cannot report to anyone")
                return (True, None)

            # Non-CEO must have a parent
            if parent_node_id is None:
                valid_levels = get_valid_parent_levels(employee_hierarchy_level)
                valid_level_names = [HIERARCHY_LEVELS[l] for l in valid_levels]
                return (
                    False,
                    f"Level {employee_hierarchy_level} ({HIERARCHY_LEVELS[employee_hierarchy_level]}) must report to someone. "
                    f"Valid parent levels: {', '.join(valid_level_names)} (levels {valid_levels})"
                )

            # Get the parent node
            parent = session.query(OrgNode).filter(OrgNode.id == parent_node_id).first()

            if not parent:
                return (False, f"Parent node not found: {parent_node_id}")

            # Check hierarchy level - parent must be at higher level (lower number within allowed range)
            parent_level = parent.hierarchy_level
            valid_parent_levels = get_valid_parent_levels(employee_hierarchy_level)

            if parent_level not in valid_parent_levels:
                valid_level_names = [HIERARCHY_LEVELS[l] for l in valid_parent_levels]
                return (
                    False,
                    f"{HIERARCHY_LEVELS[employee_hierarchy_level]} (Level {employee_hierarchy_level}) cannot report to "
                    f"{HIERARCHY_LEVELS[parent_level]} (Level {parent_level}). "
                    f"Valid parent levels: {', '.join(valid_level_names)} (levels {valid_parent_levels})"
                )

            # Check specialization alignment
            # Only enforce specialization match for non-executive roles (levels < 13)
            if employee_hierarchy_level < 13 and parent_level < 13:  # Both are non-executive
                if parent.specialization != employee_specialization:
                    return (
                        False,
                        f"{HIERARCHY_LEVELS[employee_hierarchy_level]} in {employee_specialization} cannot report to "
                        f"{HIERARCHY_LEVELS[parent_level]} in {parent.specialization}. "
                        f"Reporting must stay within same specialization domain."
                    )

            # Check business unit consistency (within same BU unless parent is org-wide)
            if business_unit_id and parent.business_unit_id:
                # Org-wide roles (CFO, CWP) can manage across BUs
                parent_is_org_wide = parent.hierarchy_level >= 16  # Partner or CEO level
                if not parent_is_org_wide and parent.business_unit_id != business_unit_id:
                    return (
                        False,
                        f"Employee is in BU {business_unit_id} but reports to someone in BU {parent.business_unit_id}. "
                        f"Reporting must be within same BU (unless parent is org-wide role like CFO/CWP)."
                    )

            # Check for circular reporting (would create a loop)
            if OrgHierarchyValidator._has_circular_reporting(
                session, parent_node_id, parent_node_id
            ):
                return (False, "Circular reporting detected - would create infinite loop")

            return (True, None)

        except Exception as e:
            logger.error(f"Reporting validation error: {e}", exc_info=True)
            return (False, f"Validation error: {str(e)}")

    @staticmethod
    def _has_circular_reporting(
        session: Session, node_id: str, check_against_id: str, visited: set = None
    ) -> bool:
        """Check if assigning parent would create circular reporting"""
        if visited is None:
            visited = set()

        if node_id in visited:
            return True

        visited.add(node_id)

        node = session.query(OrgNode).filter(OrgNode.id == node_id).first()

        if not node or not node.parent_node_id:
            return False

        if node.parent_node_id == check_against_id:
            return True

        return OrgHierarchyValidator._has_circular_reporting(
            session, node.parent_node_id, check_against_id, visited
        )

    @staticmethod
    def get_valid_supervisors(
        session: Session,
        employee_hierarchy_level: int,
        employee_specialization: str,
        business_unit_id: Optional[str] = None,
    ) -> list:
        """
        Get list of valid supervisors for an employee

        Returns list of OrgNode records that can supervise this employee
        """
        try:
            valid_parent_levels = get_valid_parent_levels(employee_hierarchy_level)

            query = session.query(OrgNode).filter(
                OrgNode.hierarchy_level.in_(valid_parent_levels)
            )

            # Filter by specialization (non-executive roles must match specialization)
            if employee_hierarchy_level < 13:
                query = query.filter(OrgNode.specialization == employee_specialization)

            # Filter by business unit if specified
            if business_unit_id:
                query = query.filter(
                    (OrgNode.business_unit_id == business_unit_id)
                    | (OrgNode.hierarchy_level >= 16)  # Org-wide roles (Partner/CEO)
                )

            return query.all()

        except Exception as e:
            logger.error(f"Error getting valid supervisors: {e}")
            return []

    @staticmethod
    def print_hierarchy_rules():
        """Print the hierarchy rules for documentation"""
        print("\n" + "=" * 80)
        print("ORGANIZATIONAL HIERARCHY RULES (17 LEVELS + SPECIALIZATIONS)")
        print("=" * 80)

        for level in range(1, 18):
            level_name = HIERARCHY_LEVELS[level]
            valid_parents = get_valid_parent_levels(level)
            parent_names = [f"{HIERARCHY_LEVELS[p]} (L{p})" for p in valid_parents]
            parents_str = ", ".join(parent_names) if parent_names else "(top level - reports to nobody)"

            print(f"\nLevel {level}: {level_name}")
            print(f"  └─ Reports to: {parents_str}")

        print("\n" + "=" * 80)
        print("SPECIALIZATIONS:")
        for spec in SPECIALIZATIONS:
            print(f"  • {spec}")
        print("\n" + "=" * 80)
        print("RULES:")
        print("  1. Cannot skip more than 2 levels (employee can report up max 2 levels)")
        print("  2. Parent must be at higher level (lower hierarchy_level number)")
        print("  3. Non-executive roles must report within same specialization")
        print("  4. Same business unit unless parent is org-wide (Partner/CEO)")
        print("  5. No circular reporting chains")
        print("=" * 80 + "\n")


def validate_before_employee_creation(
    session: Session,
    hierarchy_level: int,
    specialization: str,
    parent_node_id: Optional[str],
    business_unit_id: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Wrapper function for employee creation validation

    Call this BEFORE creating a new OrgNode or user

    Returns:
        (is_valid, error_message)
    """
    return OrgHierarchyValidator.validate_reporting_relationship(
        session, hierarchy_level, specialization, parent_node_id, business_unit_id
    )
