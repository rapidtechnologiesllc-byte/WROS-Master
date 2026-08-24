/**
 * Permission-based access control utilities for frontend
 *
 * Provides functions to check user permissions based on role template assignments.
 * Permissions follow the format: 'resource.action' (e.g., 'administration.view', 'candidates.create')
 *
 * Actions are:
 * - view (V): User can view/access the module
 * - create (C): User can create new items
 * - edit (E): User can edit existing items
 * - delete (D): User can delete items
 */

/**
 * Get user's current permissions from localStorage or state
 * @returns {Array<string>} Array of permission strings
 */
export const getUserPermissions = () => {
  try {
    const userStr = localStorage.getItem('user');
    if (!userStr) return [];

    const user = JSON.parse(userStr);
    return user.permissions || [];
  } catch (error) {
    console.error('Failed to get user permissions from localStorage:', error);
    return [];
  }
};

/**
 * Check if user has a specific permission
 * @param {string} permission - Permission string (e.g., 'candidates.view')
 * @returns {boolean} True if user has permission
 */
export const hasPermission = (permission) => {
  const permissions = getUserPermissions();
  return permissions.includes(permission.toLowerCase());
};

/**
 * Check if user has any of the given permissions
 * @param {Array<string>} permissions - Array of permission strings
 * @returns {boolean} True if user has at least one permission
 */
export const hasAnyPermission = (permissions) => {
  const userPerms = getUserPermissions();
  return permissions.some(perm => userPerms.includes(perm.toLowerCase()));
};

/**
 * Check if user has all of the given permissions
 * @param {Array<string>} permissions - Array of permission strings
 * @returns {boolean} True if user has all permissions
 */
export const hasAllPermissions = (permissions) => {
  const userPerms = getUserPermissions();
  return permissions.every(perm => userPerms.includes(perm.toLowerCase()));
};

/**
 * Check if user is super admin (can access everything)
 * @returns {boolean} True if user is super admin
 */
export const isSuperAdmin = () => {
  try {
    const userStr = localStorage.getItem('user');
    if (!userStr) return false;

    const user = JSON.parse(userStr);
    return user.is_super_admin === true;
  } catch (error) {
    console.error('Failed to check super admin status:', error);
    return false;
  }
};

// ============================================================================
// MODULE-LEVEL PERMISSION HELPERS
// ============================================================================

/**
 * Check if user can view a specific module
 * @param {string} moduleName - Module name (e.g., 'administration', 'recruitment')
 * @returns {boolean} True if user can view the module
 */
export const canViewModule = (moduleName) => {
  return hasPermission(`${moduleName}.view`);
};

/**
 * Check if user can create in a specific module
 * @param {string} moduleName - Module name
 * @returns {boolean} True if user can create in the module
 */
export const canCreateInModule = (moduleName) => {
  return hasPermission(`${moduleName}.create`);
};

/**
 * Check if user can edit in a specific module
 * @param {string} moduleName - Module name
 * @returns {boolean} True if user can edit in the module
 */
export const canEditInModule = (moduleName) => {
  return hasPermission(`${moduleName}.edit`);
};

/**
 * Check if user can delete in a specific module
 * @param {string} moduleName - Module name
 * @returns {boolean} True if user can delete in the module
 */
export const canDeleteInModule = (moduleName) => {
  return hasPermission(`${moduleName}.delete`);
};

/**
 * Check if user has any action permission in a module
 * @param {string} moduleName - Module name
 * @returns {boolean} True if user has any permission (view, create, edit, or delete)
 */
export const hasAnyModulePermission = (moduleName) => {
  return hasAnyPermission([
    `${moduleName}.view`,
    `${moduleName}.create`,
    `${moduleName}.edit`,
    `${moduleName}.delete`
  ]);
};

// ============================================================================
// SPECIFIC MODULE PERMISSION CHECKS
// ============================================================================

/**
 * Administration module permissions (Users, Business Units, Role Templates)
 */
export const administration = {
  canView: () => canViewModule('administration'),
  canCreate: () => canCreateInModule('administration'),
  canEdit: () => canEditInModule('administration'),
  canDelete: () => canDeleteInModule('administration'),
  canManage: () => hasAllPermissions(['administration.view', 'administration.create', 'administration.edit'])
};

/**
 * Recruitment module permissions
 */
export const recruitment = {
  canView: () => canViewModule('recruitment'),
  canCreate: () => canCreateInModule('recruitment'),
  canEdit: () => canEditInModule('recruitment'),
  canDelete: () => canDeleteInModule('recruitment'),
  canManage: () => hasAllPermissions(['recruitment.view', 'recruitment.create', 'recruitment.edit'])
};

/**
 * Candidates module permissions
 */
export const candidates = {
  canView: () => canViewModule('candidates'),
  canCreate: () => canCreateInModule('candidates'),
  canEdit: () => canEditInModule('candidates'),
  canDelete: () => canDeleteInModule('candidates'),
  canManage: () => hasAllPermissions(['candidates.view', 'candidates.create', 'candidates.edit'])
};

/**
 * Projects module permissions
 */
export const projects = {
  canView: () => canViewModule('projects'),
  canCreate: () => canCreateInModule('projects'),
  canEdit: () => canEditInModule('projects'),
  canDelete: () => canDeleteInModule('projects'),
  canManage: () => hasAllPermissions(['projects.view', 'projects.create', 'projects.edit'])
};

/**
 * Finance module permissions
 */
export const finance = {
  canView: () => canViewModule('finance'),
  canCreate: () => canCreateInModule('finance'),
  canEdit: () => canEditInModule('finance'),
  canDelete: () => canDeleteInModule('finance'),
  canManage: () => hasAllPermissions(['finance.view', 'finance.create', 'finance.edit'])
};

/**
 * Reports module permissions
 */
export const reports = {
  canView: () => canViewModule('reports'),
  canCreate: () => canCreateInModule('reports'),
  canEdit: () => canEditInModule('reports'),
  canDelete: () => canDeleteInModule('reports')
};

/**
 * Workforce module permissions
 */
export const workforce = {
  canView: () => canViewModule('workforce'),
  canCreate: () => canCreateInModule('workforce'),
  canEdit: () => canEditInModule('workforce'),
  canDelete: () => canDeleteInModule('workforce'),
  canManage: () => hasAllPermissions(['workforce.view', 'workforce.create', 'workforce.edit'])
};

// ============================================================================
// UI HELPER FUNCTIONS
// ============================================================================

/**
 * Get permission error message for UI display
 * @param {string} action - Action type (view, create, edit, delete)
 * @param {string} resource - Resource name
 * @returns {string} User-friendly error message
 */
export const getPermissionErrorMessage = (action, resource) => {
  const actionText = {
    view: 'access',
    create: 'create items in',
    edit: 'edit items in',
    delete: 'delete items in'
  }[action] || 'access';

  return `You don't have permission to ${actionText} ${resource}`;
};

/**
 * Get permission denied tooltip text
 * @param {string} permission - Permission string
 * @returns {string} Tooltip text
 */
export const getPermissionTooltip = (permission) => {
  const [resource, action] = permission.split('.');
  const actionText = {
    view: 'View',
    create: 'Create',
    edit: 'Edit',
    delete: 'Delete'
  }[action] || 'Access';

  return `Permission required: ${actionText} ${resource}`;
};

// ============================================================================
// PERMISSION VALIDATION
// ============================================================================

/**
 * Validate that user has required permissions before performing action
 * @param {string|Array} requiredPermissions - Permission string or array of strings
 * @param {function} onGranted - Callback if permission is granted
 * @param {function} onDenied - Callback if permission is denied (optional)
 * @returns {void}
 */
export const validatePermission = (requiredPermissions, onGranted, onDenied = null) => {
  const permissions = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];

  if (hasAllPermissions(permissions)) {
    onGranted();
  } else {
    if (onDenied) {
      onDenied();
    } else {
      console.warn('Permission denied:', requiredPermissions);
    }
  }
};

/**
 * Check if a navigation item should be visible based on user permissions
 * @param {string} moduleName - Module name for the nav item
 * @returns {boolean} True if user can view the module
 */
export const isNavItemVisible = (moduleName) => {
  return canViewModule(moduleName);
};

/**
 * Get visible navigation modules for the user
 * @param {Array} allModules - All available modules
 * @returns {Array} Modules the user can access
 */
export const getVisibleModules = (allModules) => {
  return allModules.filter(module => isNavItemVisible(module.key));
};

/**
 * Cache permissions in localStorage for performance
 * (Called after login to cache user's permissions)
 * @param {Object} user - User object with permissions array
 * @returns {void}
 */
export const cacheUserPermissions = (user) => {
  try {
    localStorage.setItem('user', JSON.stringify(user));
  } catch (error) {
    console.error('Failed to cache user permissions:', error);
  }
};

/**
 * Clear cached permissions (Call on logout)
 * @returns {void}
 */
export const clearCachedPermissions = () => {
  try {
    localStorage.removeItem('user');
  } catch (error) {
    console.error('Failed to clear cached permissions:', error);
  }
};
