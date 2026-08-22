/**
 * Frontend permission checking utility - checks permissions from role templates
 * Complements backend RoleTemplatePermissionService
 */

export const getStoredPermissions = () => {
  try {
    const perms = localStorage.getItem('hrms_permissions');
    if (!perms) return null;

    const parsed = JSON.parse(perms);
    // Could be array (legacy) or object (role template)
    return parsed;
  } catch (e) {
    console.warn('Failed to parse permissions:', e);
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
