"""Data Healer Service - Fixes candidate data issues and uses placeholders for failed creation

When candidate creation fails due to data quality issues:
1. Attempt to heal/fix the data using available validation
2. If fixable, return healed data for retry
3. If not fixable, provide placeholder values to unblock creation
4. Create recruiter task to fix the candidate details later
"""
import logging
import re
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

from app.core.logging import logger

logger = logging.getLogger(__name__)


class DataHealerService:
    """Heals data quality issues to unblock candidate creation"""

    PLACEHOLDER_VALUES = {
        'email': 'pending-email-{timestamp}@placeholder.local',
        'phone': '+1-555-0000',
        'location': 'Not Specified',
        'name': 'Pending Name',
        'title': 'Not Specified',
    }

    @staticmethod
    def heal_and_recover(
        error: str,
        payload: Dict[str, Any],
        db = None  # Optional DB connection for validation
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Attempt to heal data issues and provide recovery strategy.

        Args:
            error: Error message from failed candidate creation
            payload: Candidate payload that failed
            db: Optional database session

        Returns:
            (can_continue: bool, healed_payload: dict, recruiter_task: str or None)
            - can_continue=True: Use healed_payload to retry
            - can_continue=False: Cannot heal, creation will be blocked
            - recruiter_task: Task description for recruiter if using placeholders
        """
        logger.info(f"[Healer] Attempting to heal: {error}")

        # Strategy 1: Missing required fields - use placeholders
        if "missing" in error.lower() or "null" in error.lower() or "required" in error.lower():
            return DataHealerService._heal_missing_fields(error, payload)

        # Strategy 2: Invalid format - try to fix
        if "invalid" in error.lower() or "format" in error.lower():
            return DataHealerService._heal_invalid_format(error, payload)

        # Strategy 3: Duplicate detection - allow creation (duplicates tracked separately)
        if "duplicate" in error.lower():
            logger.info("[Healer] Duplicate candidate - allowing creation with multiple app tracking")
            return True, payload, None

        # Strategy 4: Database constraint - use placeholder for problematic field
        if "constraint" in error.lower() or "unique" in error.lower():
            return DataHealerService._heal_constraint_violation(error, payload)

        # Cannot heal - propagate error
        logger.warning(f"[Healer] Cannot heal error: {error}")
        return False, {}, f"Manual review required: {error}"

    @staticmethod
    def _heal_missing_fields(error: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Heal missing required fields with placeholders."""
        healed = payload.copy()
        recruiter_tasks = []

        # Check each required field
        required_fields = {
            'candidate_email': 'email',
            'candidate_first_name': 'name',
            'candidate_current_location': 'location',
            'candidate_mobile': 'phone',
            'candidate_job_title': 'title',
        }

        fields_to_check = required_fields.items() if required_fields else []
        for field, placeholder_key in fields_to_check:
            if not payload.get(field) or str(payload.get(field)).strip() == '':
                placeholder = DataHealerService.PLACEHOLDER_VALUES.get(placeholder_key, 'Unknown')

                # For email, make timestamp-unique
                if placeholder_key == 'email':
                    timestamp = int(datetime.now().timestamp() * 1000)
                    placeholder = f"pending-{timestamp}@placeholder.local"

                healed[field] = placeholder
                recruiter_tasks.append(f"Fix {field}: currently '{placeholder}'")
                logger.info(f"[Healer] Using placeholder for {field}: {placeholder}")

        task_description = "Recruit task to fix candidate details:\n- " + "\n- ".join(recruiter_tasks)
        return True, healed, task_description

    @staticmethod
    def _heal_invalid_format(error: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Heal invalid format issues."""
        healed = payload.copy()
        recruiter_tasks = []

        # Email validation
        email = payload.get('candidate_email', '').strip()
        if email and '@' not in email:
            timestamp = int(datetime.now().timestamp() * 1000)
            healed['candidate_email'] = f"invalid-{timestamp}@placeholder.local"
            recruiter_tasks.append(f"Email format invalid: '{email}' → requires valid email")
            logger.info("[Healer] Fixed email format")

        # Phone validation
        phone = (payload.get('candidate_mobile') or '').strip()
        if phone and not re.match(r'^[\d\s\-\+\(\)]+$', phone):
            healed['candidate_mobile'] = '+1-555-0000'
            recruiter_tasks.append(f"Phone format invalid: '{phone}' → fixed to placeholder")
            logger.info("[Healer] Fixed phone format")

        # Name validation
        name = (payload.get('candidate_first_name') or '').strip()
        if name and len(name) < 2:
            healed['candidate_first_name'] = 'Unknown'
            recruiter_tasks.append(f"First name too short: '{name}' → set to 'Unknown'")
            logger.info("[Healer] Fixed first name")

        if not recruiter_tasks:
            # No fixable issues found
            logger.warning(f"[Healer] Could not heal format issue: {error}")
            return False, {}, f"Format issue cannot be auto-fixed: {error}"

        task_description = "Recruit task to fix candidate details:\n- " + "\n- ".join(recruiter_tasks)
        return True, healed, task_description

    @staticmethod
    def _heal_constraint_violation(error: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Heal database constraint violations with placeholder values."""
        healed = payload.copy()
        recruiter_tasks = []

        # For unique constraints on email or phone, use timestamp-based placeholder
        if "email" in error.lower():
            timestamp = int(datetime.now().timestamp() * 1000)
            healed['candidate_email'] = f"unique-{timestamp}@placeholder.local"
            recruiter_tasks.append(f"Email constraint violated → using unique placeholder")
            logger.info("[Healer] Fixed email constraint with unique placeholder")

        if "phone" in error.lower() or "mobile" in error.lower():
            healed['candidate_mobile'] = f"+1-555-{datetime.now().strftime('%m%d%S')}"
            recruiter_tasks.append(f"Phone constraint violated → using unique placeholder")
            logger.info("[Healer] Fixed phone constraint with unique placeholder")

        if not recruiter_tasks:
            logger.warning(f"[Healer] Could not heal constraint: {error}")
            return False, {}, f"Constraint violation cannot be auto-fixed: {error}"

        task_description = "Recruit task to fix candidate details:\n- " + "\n- ".join(recruiter_tasks)
        return True, healed, task_description

    @staticmethod
    def create_recruiter_fix_task(candidate_id: str, task_description: str, db=None):
        """Create a task for recruiter to fix candidate data.

        Args:
            candidate_id: ID of candidate with incomplete data
            task_description: What needs to be fixed
            db: Database session (for creating task record if available)

        Returns:
            Task ID or None if task creation not available

        TODO: Integrate with task management system to automatically create recruiter assignments
        """
        logger.info(f"[Healer] Creating recruiter task for {candidate_id}: {task_description}")

        # TODO: Implement actual task creation when task management system is available
        # Currently just logs the task for future implementation
        # Should create a Task record with:
        # - assigned_to: senior_recruiter or team_lead
        # - task_type: 'fix_candidate_data'
        # - priority: 'high'
        # - description: task_description
        # - candidate_id: candidate_id

        return None  # TODO: Integrate with task management system when available
