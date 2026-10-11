/**
 * CANONICAL PERMISSION CHECKING SYSTEM
 * Single source of truth for all permission checks
 * Handles both legacy array-based and new object-based role template permissions
 */

export const getStoredPermissions = () => {
  try {
    // Try hrms_permissions first (role template backend format)
    let perms = localStorage.getItem('hrms_permissions');
    if (perms) {
      const parsed = JSON.parse(perms);
      if (parsed && (Array.isArray(parsed) || typeof parsed === 'object')) {
        return parsed;
      }
    }

    // Fallback to legacy 'permissions' key
    perms = localStorage.getItem('permissions');
    if (perms) {
      const parsed = JSON.parse(perms);
      if (parsed && (Array.isArray(parsed) || typeof parsed === 'object')) {
        return parsed;
      }
    }

    return null;
  } catch (e) {
    console.error('Failed to parse permissions from localStorage:', e);
    return null;
  }
};

const canViewObject = (resourceName, permissions) => {
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_view || false;
  }
  return false;
};

const canCreateObject = (resourceName, permissions) => {
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_create || false;
  }
  return false;
};

const canEditObject = (resourceName, permissions) => {
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_edit || false;
  }
  return false;
};

const canDeleteObject = (resourceName, permissions) => {
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_delete || false;
  }
  return false;
};

/**
 * CANONICAL hasPermission - handles ALL permission formats robustly
 *
 * Supports:
 * 1. Array format: ["candidates", "jobs.view", "admin.*"]
 * 2. Object format: {"candidates": {can_view: true, can_create: true, ...}}
 * 3. Mixed: Tries both formats automatically
 *
 * @param {string} resourceName - Resource to check (e.g., "candidates", "jobs")
 * @param {string} action - Action to check (e.g., "view", "create", "edit", "delete")
 * @returns {boolean} True if user has permission
 */
/**
 * Role-template authority flags from the login response (server: app.core.authority).
 * The UI decides by these and by the permission matrix -- never by a role's name, and
 * there is no super-user bypass: every role sees what its modules/resources grant.
 */
export const getAuthority = () => {
  try {
    return JSON.parse(localStorage.getItem('hrms_authority') || '{}') || {};
  } catch (e) {
    console.error('Failed to parse hrms_authority from localStorage:', e);
    return {};
  }
};
export const isOrgLevel = () => Boolean(getAuthority().org_level_access);
export const isBuLeader = () => Boolean(getAuthority().is_bu_leader);
export const isFinanceLeader = () => Boolean(getAuthority().is_finance_leader);

export const hasPermission = (resourceName, action = 'view') => {
  if (!resourceName) return false;

  const permissions = getStoredPermissions();
  if (!permissions) return false;

  // Handle array-based permissions (legacy format)
  if (Array.isArray(permissions)) {
    // Wildcard check for super user

    const resourceLower = String(resourceName).toLowerCase();
    const actionLower = String(action).toLowerCase();

    // Direct resource match
    if (permissions.includes(resourceLower)) return true;

    // Exact action match (e.g., "candidates.view")
    if (permissions.includes(`${resourceLower}.${actionLower}`)) return true;

    // Wildcard module match (e.g., "candidates.*")
    if (permissions.includes(`${resourceLower}.*`)) return true;

    return false;
  }

  // Handle object-based permissions (role template format)
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    // Wildcard check

    const actionMap = {
      'view': canViewObject,
      'create': canCreateObject,
      'edit': canEditObject,
      'delete': canDeleteObject,
      'manage': (res, perms) =>
        canViewObject(res, perms) && canCreateObject(res, perms) && canEditObject(res, perms)
    };

    const checker = actionMap[action.toLowerCase()];
    if (!checker) return false;

    return checker(resourceName, permissions);
  }

  return false;
};

/**
 * Check if user has ANY permission from a list
 */
export const hasAnyPermission = (permissionList) => {
  if (!Array.isArray(permissionList)) {
    return hasPermission(permissionList);
  }
  return permissionList.some(perm => {
    if (typeof perm === 'string' && perm.includes('.')) {
      const [resource, action] = perm.split('.');
      return hasPermission(resource, action);
    }
    return hasPermission(perm);
  });
};

/**
 * Check if user has ALL permissions from a list
 */
export const hasAllPermissions = (permissionList) => {
  if (!Array.isArray(permissionList)) {
    return hasPermission(permissionList);
  }
  return permissionList.every(perm => {
    if (typeof perm === 'string' && perm.includes('.')) {
      const [resource, action] = perm.split('.');
      return hasPermission(resource, action);
    }
    return hasPermission(perm);
  });
};


/**
 * Check if user is admin (has administration.manage permission)
 */
export const isAdmin = () => hasPermission('admin-settings', 'edit');

/**
 * Get user roles array
 */
export const getRoles = () => {
  try {
    let roles = localStorage.getItem('hrms_roles');
    if (roles) {
      const parsed = JSON.parse(roles);
      if (Array.isArray(parsed)) return parsed;
    }

    roles = localStorage.getItem('roles');
    if (roles) {
      const parsed = JSON.parse(roles);
      if (Array.isArray(parsed)) return parsed;
    }

    return [];
  } catch (e) {
    console.error('Failed to get roles:', e);
    return [];
  }
};

/**
 * Get stored permissions array
 */
export const getPermissions = () => {
  const perms = getStoredPermissions();
  if (Array.isArray(perms)) return perms;
  if (typeof perms === 'object') {
    return Object.keys(perms);
  }
  return [];
};

/**
 * Get business unit id
 */
export const getBusinessUnitId = () => {
  return localStorage.getItem('business_unit_id');
};

/**
 * Get business unit name
 */


/**
 * Check if user can access full HRMS
 */


/**
 * Check if user can access workspace
 */
export const canAccessMyWorkspace = ({ permissionRole }) => {
  const role = String(permissionRole || '').trim().toLowerCase();
  return role !== 'candidate';
};

/**
 * Check if user is a candidate
 */
export const isCandidateUser = ({ role, userType }) => {
  const normalizedRole = String(role || '').trim().toUpperCase();
  if (normalizedRole === 'CANDIDATE') return true;
  const normalizedType = String(userType || '').trim().toLowerCase();
  return normalizedType === 'candidate';
};

/**
 * Get permission error message for UI display
 */


/**
 * Get permission tooltip for UI display
 */



export const canViewModule = (moduleName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  // Check if any resource in this module has view permission
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return Object.values(permissions).some(p =>
      p && (p.module_name === moduleName || p.display_name?.includes(moduleName)) && p.can_view
    );
  }

  return false;
};









/**
 * Filter navigation items by allowed modules
 */
export const filterNavigationByModules = (navigationItems, allowedModules) => {
  if (!navigationItems || navigationItems.length === 0) {
    return [];
  }

  return navigationItems.filter(item => {
    const itemModule = item.key || item.id || item.path?.split('/')[1];
    return allowedModules.includes(itemModule) || !itemModule;
  });
};

/**
 * Where an internal user lands after login: the first screen their role template lets
 * them view, most senior first. Routing config (resource -> route), not authority.
 */
const LANDING_BY_RESOURCE = [
  ['ceo-dashboard', '/ceo-fy-progress'],
  ['cfo-dashboard', '/cfo-dashboard'],
  ['partner-dashboard', '/partner-roi'],
  ['bu-head-dashboard', '/bu-dashboard'],
  ['employees', '/employees'],
  ['candidates', '/candidates'],
  ['my-tasks', '/my-tasks'],
];
export const landingPath = (fallback) => {
  const hit = LANDING_BY_RESOURCE.find(([resource]) => hasPermission(resource, 'view'));
  return hit ? hit[1] : fallback;
};
