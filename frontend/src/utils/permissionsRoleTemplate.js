
export const getStoredPermissions = () => {
  try {
    const perms = localStorage.getItem('hrms_permissions');
    if (!perms) return null;

    const parsed = JSON.parse(perms);
    // Could be array (legacy) or object (role template)
    return parsed;
  } catch (e) {
    console.error('Failed to parse permissions from localStorage:', e);
    return null;
  }
};

export const canView = (resourceName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  // Handle object-based permissions (resource_name: {can_view: true, ...})
  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_view || false;
  }

  return false;
};

export const canCreate = (resourceName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_create || false;
  }

  return false;
};

export const canEdit = (resourceName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_edit || false;
  }

  return false;
};

export const canDelete = (resourceName) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  if (typeof permissions === 'object' && !Array.isArray(permissions)) {
    return permissions[resourceName]?.can_delete || false;
  }

  return false;
};

export const hasPermission = (resourceName, action) => {
  const permissions = getStoredPermissions();
  if (!permissions) return false;

  // Handle array-based permissions (array of permission strings)
  if (Array.isArray(permissions)) {
    return permissions.includes(resourceName);
  }

  // Handle object-based permissions (resource_name: {can_view: true, ...})
  const actionMap = {
    'view': canView,
    'create': canCreate,
    'edit': canEdit,
    'delete': canDelete,
  };

  const checker = actionMap[action];
  if (!checker) return false;

  return checker(resourceName);
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
