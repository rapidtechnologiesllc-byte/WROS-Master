// Permission checking utilities

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

export const hasAllPermissions = (userPermissions, permissionNames) => {
  return permissionNames.every(perm => hasPermission(userPermissions, perm));
};

export const hasAnyPermission = (userPermissions, permissionNames) => {
  return permissionNames.some(perm => hasPermission(userPermissions, perm));
};

export const canDo = (userPermissions, module, verb) => {
  return hasPermission(userPermissions, `${module}_${verb}`);
};





export const canEdit = (userPermissions, module) => {
  return canDo(userPermissions, module, "edit");
};

export const canDelete = (userPermissions, module) => {
  return canDo(userPermissions, module, "delete");
};
