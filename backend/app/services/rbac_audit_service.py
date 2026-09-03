"""
import logging
DEPRECATED: RBAC audit service stub for backwards compatibility.

The RBAC Permission system has been deprecated in favor of RoleTemplate-based permissions.
This stub file prevents import errors during the transition period.
"""

import logging
from app.core.logging import logger
logger = logging.getLogger(__name__)

class RBACauditService:
    """Deprecated RBAC audit service - stub for backwards compatibility."""

    @staticmethod
    def log_rbac_change(*args, **kwargs):
        """Stub: Do nothing."""
        pass

    @staticmethod
    def get_audit_log(*args, **kwargs):
        """Stub: Return empty list."""
        return []
