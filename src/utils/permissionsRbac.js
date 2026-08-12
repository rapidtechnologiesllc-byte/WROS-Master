// RBAC permission utilities for multi-role support
// Supports both legacy role-based and new permission-based checks

export const getPermissions = () => {
  const stored = localStorage.getItem("hrms_permissions");
  return stored ? JSON.parse(stored) : [];
};

export const getRoles = () => {
  const stored = localStorage.getItem("hrms_roles");
  return stored ? JSON.parse(stored) : [];
};

export const getBusinessUnitId = () => {
  const stored = localStorage.getItem("hrms_business_unit_id");
  return stored ? parseInt(stored, 10) : null;
};

export const getBusinessUnitName = () => {
  return localStorage.getItem("hrms_business_unit_name") || "Default BU";
};

// Check if user has a specific permission
export const hasPermission = (permission) => {
  const permissions = getPermissions();
  if (!Array.isArray(permissions)) return false;

  // Check exact permission match
  if (permissions.includes(permission)) return true;

  // Check wildcard permissions (e.g., "recruitment.*" matches "recruitment.view")
  const [module, verb] = permission.split(".");
  if (module && verb) {
    if (permissions.includes(`${module}.*`)) return true;
    if (permissions.includes("*.*")) return true; // Super user
  }

  return false;
};

// Check if user has any of the given permissions
export const hasAnyPermission = (permissionList) => {
  return Array.isArray(permissionList) && permissionList.some(perm => hasPermission(perm));
};

// Check if user has all of the given permissions
export const hasAllPermissions = (permissionList) => {
  return Array.isArray(permissionList) && permissionList.every(perm => hasPermission(perm));
};

// Check if user has a specific role
export const hasRole = (roleName) => {
  const roles = getRoles();
  if (!Array.isArray(roles)) return false;
  return roles.map(r => String(r).toUpperCase()).includes(String(roleName).toUpperCase());
};

// Check if user has any of the given roles
export const hasAnyRole = (roleList) => {
  return Array.isArray(roleList) && roleList.some(role => hasRole(role));
};

// Check if user is super user
export const isSuperUser = () => {
  return hasPermission("*.*") || hasRole("SUPER_USER") || hasRole("SUPER USER");
};

// Check if user is admin
export const isAdmin = () => {
  return hasRole("ADMIN") || isSuperUser();
};

// Get roles list with display names
export const getRolesList = () => {
  const roles = getRoles();
  if (!Array.isArray(roles)) return [];
  return roles.map(r => String(r).trim()).filter(Boolean);
};

// Navigation item visibility helper
export const shouldShowNavItem = (requiredPermissions) => {
  if (!requiredPermissions) return true;
  if (typeof requiredPermissions === "string") {
    return hasPermission(requiredPermissions);
  }
  if (Array.isArray(requiredPermissions)) {
    return hasAnyPermission(requiredPermissions);
  }
  return true;
};

// UI element visibility helper
export const canViewModule = (moduleName) => {
  return hasPermission(`${moduleName}.view`) || hasPermission(`${moduleName}.*`);
};

export const canCreateInModule = (moduleName) => {
  return hasPermission(`${moduleName}.create`) || hasPermission(`${moduleName}.*`);
};

export const canEditInModule = (moduleName) => {
  return hasPermission(`${moduleName}.edit`) || hasPermission(`${moduleName}.*`);
};

export const canDeleteInModule = (moduleName) => {
  return hasPermission(`${moduleName}.delete`) || hasPermission(`${moduleName}.*`);
};

export const canManageInModule = (moduleName) => {
  return hasPermission(`${moduleName}.manage`) || hasPermission(`${moduleName}.*`);
};
