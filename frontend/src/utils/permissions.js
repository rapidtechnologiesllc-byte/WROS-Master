const normalizeRole = (role) =>
  String(role || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "_");

export const ROLES = Object.freeze({
  SUPER_USER: "SUPER_USER",
  CANDIDATE: "CANDIDATE",
});

export const getNormalizedRole = (role) => normalizeRole(role);

export const isSuperUserRole = (role) =>
  normalizeRole(role) === ROLES.SUPER_USER;

export const isCandidateRole = (role) =>
  normalizeRole(role) === ROLES.CANDIDATE;

export const isCandidateUser = ({ role, userType }) =>
  isCandidateRole(role) ||
  String(userType || "")
    .trim()
    .toLowerCase() === "candidate";

export const canAccessFullHrms = ({ role }) => {
  return isSuperUserRole(role);
};

export const canAccessMyWorkspace = ({ permissionRole, jobTitle }) => {
  const role = String(permissionRole || "")
    .trim()
    .toLowerCase();
  return jobTitle === 'Super User' || role !== "candidate";
};

// ============ NEW RBAC SYSTEM ============
// Permission checking against localStorage (set by AuthPage.js after login)

export function hasPermission(permission) {
  // Try new RBAC system first (hrms_permissions from role template backend)
  let permissions = JSON.parse(localStorage.getItem('hrms_permissions') || '[]');

  // Fall back to legacy 'permissions' key
  if (!permissions || permissions.length === 0) {
    permissions = JSON.parse(localStorage.getItem('permissions') || '[]');
  }

  if (!Array.isArray(permissions)) return false;

  // Wildcard check for super user
  if (permissions.includes('*.*')) return true;

  // Direct permission match (e.g., "candidates", "jobs")
  if (permissions.includes(permission)) return true;

  // Exact action match (e.g., "candidates.view", "jobs.create")
  if (permissions.includes(`${permission}.view`) ||
      permissions.includes(`${permission}.create`) ||
      permissions.includes(`${permission}.edit`) ||
      permissions.includes(`${permission}.delete`)) {
    return true;
  }

  // Wildcard module match (e.g., candidate.* matches candidate.view)
  const parts = permission.split('.');
  if (parts.length === 2) {
    const moduleWildcard = `${parts[0]}.*`;
    if (permissions.includes(moduleWildcard)) return true;
  }

  return false;
}

export function hasAnyPermission(permissionList) {
  if (!Array.isArray(permissionList)) return false;
  return permissionList.some(perm => hasPermission(perm));
}

export function hasAllPermissions(permissionList) {
  if (!Array.isArray(permissionList)) return false;
  return permissionList.every(perm => hasPermission(perm));
}

export function hasRole(roleName) {
  // Try new RBAC system first (hrms_roles from backend)
  let roles = JSON.parse(localStorage.getItem('hrms_roles') || '[]');

  // Fall back to legacy 'roles' key
  if (!roles || roles.length === 0) {
    roles = JSON.parse(localStorage.getItem('roles') || '[]');
  }

  if (!Array.isArray(roles)) return false;
  return roles.some(role => role.toLowerCase() === roleName.toLowerCase());
}

/**
 * RBAC-driven: Check if user has wildcard permission ('*.*')
 * This permission is ONLY assigned by the SuperUser role template
 * NOT based on hardcoded role name matching
 */
export function isSuperUser() {
  let permissions = JSON.parse(localStorage.getItem('hrms_permissions') || '[]');

  if (!permissions || permissions.length === 0) {
    permissions = JSON.parse(localStorage.getItem('permissions') || '[]');
  }

  // ONLY check for wildcard permission (assigned by role template)
  // Do NOT check for hardcoded role names like 'super user' or 'admin'
  return Array.isArray(permissions) && permissions.includes('*.*');
}

/**
 * RBAC-driven: Check if user has 'administration.manage' permission
 * This permission is assigned by the Admin role template
 * NOT based on hardcoded role name matching
 */
export function isAdmin() {
  // Check for administration.manage permission (assigned by Admin role template)
  // Do NOT check for hardcoded role names
  return hasPermission('administration.manage');
}

export function getRoles() {
  // Try new RBAC system first (hrms_roles from backend)
  let roles = JSON.parse(localStorage.getItem('hrms_roles') || '[]');

  // Fall back to legacy 'roles' key
  if (!roles || roles.length === 0) {
    roles = JSON.parse(localStorage.getItem('roles') || '[]');
  }

  return Array.isArray(roles) ? roles : [];
}

export function getPermissions() {
  // Try new RBAC system first (hrms_permissions from role template backend)
  let permissions = JSON.parse(localStorage.getItem('hrms_permissions') || '[]');

  // Fall back to legacy 'permissions' key
  if (!permissions || permissions.length === 0) {
    permissions = JSON.parse(localStorage.getItem('permissions') || '[]');
  }

  return Array.isArray(permissions) ? permissions : [];
}

export function getBusinessUnitId() {
  return localStorage.getItem('business_unit_id');
}

export function getBusinessUnitName() {
  return localStorage.getItem('business_unit_name');
}

export function canViewModule(moduleName) {
  return hasPermission(`${moduleName}.view`);
}

export function canCreateInModule(moduleName) {
  return hasPermission(`${moduleName}.create`);
}

export function canEditInModule(moduleName) {
  return hasPermission(`${moduleName}.edit`);
}

export function canDeleteInModule(moduleName) {
  return hasPermission(`${moduleName}.delete`);
}

export function canManageModule(moduleName) {
  return hasPermission(`${moduleName}.manage`);
}
