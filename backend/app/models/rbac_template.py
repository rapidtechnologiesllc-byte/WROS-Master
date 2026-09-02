"""
Compatibility stub for legacy RBAC tests.
RBAC system has been removed - use RoleTemplate system instead.
This module only exists to prevent import errors in legacy tests.
import logging
"""

# Stub classes for backward compatibility
class BusinessUnit:
    pass
logger = logging.getLogger(__name__)

class Permission:
    pass

class Role:
    pass

class RoleAttribute:
    pass

class RolePermission:
    pass
