// Permission checking utilities

/**
 * Check if user has a specific permission
 * @param {object} userPermissions - User's permission overrides from API
 * @param {string} permissionName - Permission to check (e.g., "candidates_view", "jobs_edit")
 * @returns {boolean} true if user has permission
 */
export const hasPermission = (userPermissions, permissionName) => {
  if (!userPermissions) return true; // Default to allow if no permissions data

  const permKey = `perm_${permissionName}`;

  // If permission is explicitly in overrides, use that value
  if (permKey in userPermissions) {
    return userPermissions[permKey];
  }

  // Default to true (allow) if not overridden
  return true;
};

/**
 * Check multiple permissions (AND logic)
 * @param {object} userPermissions - User's permission overrides
 * @param {string[]} permissionNames - Permissions to check
 * @returns {boolean} true if user has ALL permissions
 */
export const hasAllPermissions = (userPermissions, permissionNames) => {
  return permissionNames.every(perm => hasPermission(userPermissions, perm));
};

/**
 * Check multiple permissions (OR logic)
 * @param {object} userPermissions - User's permission overrides
 * @param {string[]} permissionNames - Permissions to check
 * @returns {boolean} true if user has ANY permission
 */
export const hasAnyPermission = (userPermissions, permissionNames) => {
  return permissionNames.some(perm => hasPermission(userPermissions, perm));
};

/**
 * Get permission status for a module-verb pair
 * @param {object} userPermissions - User's permission overrides
 * @param {string} module - Module name (e.g., "candidates")
 * @param {string} verb - Verb (view, create, edit, delete)
 * @returns {boolean} true if user has permission
 */
export const canDo = (userPermissions, module, verb) => {
  return hasPermission(userPermissions, `${module}_${verb}`);
};

/**
 * Check if user can view a resource
 */
export const canView = (userPermissions, module) => {
  return canDo(userPermissions, module, "view");
};

/**
 * Check if user can create a resource
 */
export const canCreate = (userPermissions, module) => {
  return canDo(userPermissions, module, "create");
};

/**
 * Check if user can edit a resource
 */
export const canEdit = (userPermissions, module) => {
  return canDo(userPermissions, module, "edit");
};

/**
 * Check if user can delete a resource
 */
export const canDelete = (userPermissions, module) => {
  return canDo(userPermissions, module, "delete");
};
