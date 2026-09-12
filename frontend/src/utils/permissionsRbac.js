
export const getUserPermissions = () => {
  try {
    const permissionsStr = localStorage.getItem('hrms_permissions');
    if (!permissionsStr) return [];

    const permissions = JSON.parse(permissionsStr);
    return permissions || [];
  } catch (error) {
    console.error('Failed to get user permissions from localStorage:', error);
    // CRITICAL FIX: Throw security error instead of silent failure
    throw new Error(`Failed to load permissions from storage: ${error.message}`);
  }
};

export const hasPermission = (permission) => {
  const permissions = getUserPermissions();
  return permissions.includes(permission.toLowerCase());
};

export const hasAnyPermission = (permissions) => {
  const userPerms = getUserPermissions();
  return permissions.some(perm => userPerms.includes(perm.toLowerCase()));
};

export const hasAllPermissions = (permissions) => {
  const userPerms = getUserPermissions();
  return permissions.every(perm => userPerms.includes(perm.toLowerCase()));
};

export const isSuperAdmin = () => {
  try {
    // Check if user has wildcard permission (assigned by SuperUser role template)
    return hasPermission('*.*');
  } catch (error) {
    console.error('Failed to check super admin status:', error);
    // CRITICAL FIX: Throw security error instead of silent failure
    throw new Error(`Failed to verify admin status: ${error.message}`);
  }
};

// MODULE-LEVEL PERMISSION HELPERS

export const canViewModule = (moduleName) => {
  return hasPermission(`${moduleName}.view`);
};

export const canCreateInModule = (moduleName) => {
  return hasPermission(`${moduleName}.create`);
};

export const canEditInModule = (moduleName) => {
  return hasPermission(`${moduleName}.edit`);
};

export const canDeleteInModule = (moduleName) => {
  return hasPermission(`${moduleName}.delete`);
};

export const hasAnyModulePermission = (moduleName) => {
  return hasAnyPermission([
    `${moduleName}.view`,
    `${moduleName}.create`,
    `${moduleName}.edit`,
    `${moduleName}.delete`
  ]);
};

// SPECIFIC MODULE PERMISSION CHECKS

export const administration = {
  canView: () => canViewModule('administration'),
  canCreate: () => canCreateInModule('administration'),
  canEdit: () => canEditInModule('administration'),
  canDelete: () => canDeleteInModule('administration'),
  canManage: () => hasAllPermissions(['administration.view', 'administration.create', 'administration.edit'])
};

export const recruitment = {
  canView: () => canViewModule('recruitment'),
  canCreate: () => canCreateInModule('recruitment'),
  canEdit: () => canEditInModule('recruitment'),
  canDelete: () => canDeleteInModule('recruitment'),
  canManage: () => hasAllPermissions(['recruitment.view', 'recruitment.create', 'recruitment.edit'])
};

export const candidates = {
  canView: () => canViewModule('candidates'),
  canCreate: () => canCreateInModule('candidates'),
  canEdit: () => canEditInModule('candidates'),
  canDelete: () => canDeleteInModule('candidates'),
  canManage: () => hasAllPermissions(['candidates.view', 'candidates.create', 'candidates.edit'])
};

export const projects = {
  canView: () => canViewModule('projects'),
  canCreate: () => canCreateInModule('projects'),
  canEdit: () => canEditInModule('projects'),
  canDelete: () => canDeleteInModule('projects'),
  canManage: () => hasAllPermissions(['projects.view', 'projects.create', 'projects.edit'])
};

export const finance = {
  canView: () => canViewModule('finance'),
  canCreate: () => canCreateInModule('finance'),
  canEdit: () => canEditInModule('finance'),
  canDelete: () => canDeleteInModule('finance'),
  canManage: () => hasAllPermissions(['finance.view', 'finance.create', 'finance.edit'])
};

export const reports = {
  canView: () => canViewModule('reports'),
  canCreate: () => canCreateInModule('reports'),
  canEdit: () => canEditInModule('reports'),
  canDelete: () => canDeleteInModule('reports')
};

export const workforce = {
  canView: () => canViewModule('workforce'),
  canCreate: () => canCreateInModule('workforce'),
  canEdit: () => canEditInModule('workforce'),
  canDelete: () => canDeleteInModule('workforce'),
  canManage: () => hasAllPermissions(['workforce.view', 'workforce.create', 'workforce.edit'])
};

// UI HELPER FUNCTIONS

export const getPermissionErrorMessage = (action, resource) => {
  const actionText = {
    view: 'access',
    create: 'create items in',
    edit: 'edit items in',
    delete: 'delete items in'
  }[action] || 'access';

  return `You don't have permission to ${actionText} ${resource}`;
};

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

// PERMISSION VALIDATION

export const validatePermission = (requiredPermissions, onGranted, onDenied = null) => {
  const permissions = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];

  if (hasAllPermissions(permissions)) {
    onGranted();
  } else {
    if (onDenied) {
      onDenied();
    } else {
    }
  }
};

export const isNavItemVisible = (moduleName) => {
  return canViewModule(moduleName);
};

export const getVisibleModules = (allModules) => {
  return allModules.filter(module => isNavItemVisible(module.key));
};

export const cacheUserPermissions = (user) => {
  try {
    localStorage.setItem('user', JSON.stringify(user));
  } catch (error) {
    console.error('Failed to cache user permissions:', error);
    // CRITICAL FIX: Throw error instead of silent failure
    throw new Error(`Failed to cache user permissions: ${error.message}`);
  }
};

export const clearCachedPermissions = () => {
  try {
    localStorage.removeItem('user');
  } catch (error) {
    console.error('Failed to clear cached permissions:', error);
    // CRITICAL FIX: Throw error instead of silent failure
    throw new Error(`Failed to clear permissions: ${error.message}`);
  }
};

// ROLE TEMPLATE MODULE LOADING

export const filterNavigationByModules = (navigationItems, allowedModules) => {
  if (!navigationItems || navigationItems.length === 0) {
    return [];
  }

  return navigationItems.filter(item => {
    // Check if item's key/module is in allowed modules
    const itemModule = item.key || item.id || item.path?.split('/')[1];
    return allowedModules.includes(itemModule) || !itemModule;
  });
};
