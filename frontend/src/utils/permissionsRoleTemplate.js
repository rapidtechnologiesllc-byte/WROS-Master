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
export const hasPermission = (resourceName, action = 'view') => {
  if (!resourceName) return false;

  const permissions = getStoredPermissions();
  if (!permissions) return false;

  // Handle array-based permissions (legacy format)
  if (Array.isArray(permissions)) {
    // Wildcard check for super user
    if (permissions.includes('*.*') || permissions.includes('*')) return true;

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
    if (permissions['*'] || permissions['*.*']) return true;

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
 * Check if user is super admin (has wildcard permission)
 */
export const isSuperUser = () => {
  return hasPermission('*');
};

/**
 * Check if user is admin (has administration.manage permission)
 */
export const isAdmin = () => {
  return hasPermission('administration', 'manage');
};

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
export const getBusinessUnitName = () => {
  return localStorage.getItem('business_unit_name');
};

/**
 * Check if user can access full HRMS
 */
export const canAccessFullHrms = ({ role }) => {
  const normalized = String(role || '').trim().toUpperCase();
  return normalized === 'SUPER_USER' || isSuperUser();
};

/**
 * Check if user can access workspace
 */
export const canAccessMyWorkspace = ({ permissionRole, jobTitle }) => {
  const role = String(permissionRole || '').trim().toLowerCase();
  if (jobTitle === 'Super User' || isSuperUser()) return true;
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
export const getPermissionErrorMessage = (action, resource) => {
  const actionText = {
    view: 'access',
    create: 'create items in',
    edit: 'edit items in',
    delete: 'delete items in',
    manage: 'manage'
  }[action] || 'access';

  return `You don't have permission to ${actionText} ${resource}`;
};

/**
 * Get permission tooltip for UI display
 */
export const getPermissionTooltip = (permission) => {
  if (!permission || typeof permission !== 'string') {
    return 'Permission required';
  }

  const [resource, action] = permission.split('.');
  const actionText = {
    view: 'View',
    create: 'Create',
    edit: 'Edit',
    delete: 'Delete',
    manage: 'Manage'
  }[action?.toLowerCase()] || 'Access';

  return `Permission required: ${actionText} ${resource}`;
};


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

export const canCreateInModule = (moduleName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return Object.values(permissions).some(p =>
      p && (p.module_name === moduleName || p.display_name?.includes(moduleName)) && p.can_create
    );
  }

  return false;
};

export const canEditInModule = (moduleName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return Object.values(permissions).some(p =>
      p && (p.module_name === moduleName || p.display_name?.includes(moduleName)) && p.can_edit
    );
  }

  return false;
};

export const canDeleteInModule = (moduleName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return Object.values(permissions).some(p =>
      p && (p.module_name === moduleName || p.display_name?.includes(moduleName)) && p.can_delete
    );
  }

  return false;
};

export const getModulePermissions = (moduleName) => {
  return {
    canView: canViewModule(moduleName),
    canCreate: canCreateInModule(moduleName),
    canEdit: canEditInModule(moduleName),
    canDelete: canDeleteInModule(moduleName),
  };
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
