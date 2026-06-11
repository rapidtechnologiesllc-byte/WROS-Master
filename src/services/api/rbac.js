// RBAC API wrappers.
import { apiRequest } from "./client";

// Roles
export const listRoles = async () => {
  const { data } = await apiRequest("/rbac/roles", { method: "GET" });
  return data;
};

export const createRole = async (payload) => {
  const { data } = await apiRequest("/rbac/roles", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description || null,
    }),
  });
  return data;
};

export const getRoleById = async (roleId) => {
  const { data } = await apiRequest(`/rbac/roles/${roleId}`, { method: "GET" });
  return data;
};

export const assignPermissionToRole = async (roleId, permissionId) => {
  const { data } = await apiRequest(`/rbac/roles/${roleId}/permissions`, {
    method: "POST",
    body: JSON.stringify({ permission_id: permissionId }),
  });
  return data;
};

export const removePermissionFromRole = async (roleId, permissionId) => {
  const { data } = await apiRequest(
    `/rbac/roles/${roleId}/permissions/${permissionId}`,
    { method: "DELETE" },
  );
  return data;
};

// Permissions
export const listPermissions = async () => {
  const { data } = await apiRequest("/rbac/permissions", { method: "GET" });
  return data;
};

export const createPermission = async (payload) => {
  const { data } = await apiRequest("/rbac/permissions", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description || null,
    }),
  });
  return data;
};

// Business units
export const listBusinessUnits = async () => {
  const { data } = await apiRequest("/rbac/business-units", { method: "GET" });
  return data;
};

export const createBusinessUnit = async (payload) => {
  const { data } = await apiRequest("/rbac/business-units", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description || null,
    }),
  });
  return data;
};
// Departments
export const createDepartment = async (payload) => {
  const { data } = await apiRequest("/rbac/departments", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name.trim(),
      description: payload.description?.trim() || null,
    }),
  });

  return data;
};

export const departmentList = async () => {
  const { data } = await apiRequest("/rbac/departments", { method: "GET" });
  return data;
};

// User assignment
export const assignRoleToUser = async (userId, roleId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/assign-role`, {
    method: "POST",
    body: JSON.stringify({ role_id: roleId }),
  });
  return data;
};

export const setBusinessUnitForUser = async (userId, businessUnitId) => {
  const { data } = await apiRequest("/rbac/users/set-business-unit", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      business_unit_id: businessUnitId,
    }),
  });
  return data;
};

export const getUserPermissionSummary = async (userId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/permissions`, {
    method: "GET",
  });
  return data;
};

// ---------------------------------------------------------------------
// Admin maintenance (roles/permissions/business-units/user assignments)
// ---------------------------------------------------------------------

export const updateRole = async (roleId, payload) => {
  const { data } = await apiRequest(`/rbac/roles/${roleId}`, {
    method: "PUT",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description || null,
    }),
  });
  return data;
};

export const deleteRole = async (roleId) => {
  const { data } = await apiRequest(`/rbac/roles/${roleId}`, {
    method: "DELETE",
  });
  return data;
};

export const deletePermission = async (permissionId) => {
  const { data } = await apiRequest(`/rbac/permissions/${permissionId}`, {
    method: "DELETE",
  });
  return data;
};

export const updateBusinessUnit = async (businessUnitId, payload) => {
  const { data } = await apiRequest(`/rbac/business-units/${businessUnitId}`, {
    method: "PUT",
    body: JSON.stringify({
      name: payload.name,
      description: payload.description || null,
    }),
  });
  return data;
};

export const deleteBusinessUnit = async (businessUnitId) => {
  const { data } = await apiRequest(`/rbac/business-units/${businessUnitId}`, {
    method: "DELETE",
  });
  return data;
};

export const getUserRole = async (userId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/role`, {
    method: "GET",
  });
  return data;
};

export const revokeUserRole = async (userId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/role`, {
    method: "DELETE",
  });
  return data;
};

export const getUserBusinessUnit = async (userId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/business-unit`, {
    method: "GET",
  });
  return data;
};

export const updateUserBusinessUnit = async (userId, businessUnitId) => {
  const { data } = await apiRequest(`/rbac/users/${userId}/business-unit`, {
    method: "PUT",
    body: JSON.stringify({
      user_id: userId,
      business_unit_id: businessUnitId,
    }),
  });
  return data;
};
export const getDepartmentsByBusinessUnit = async (businessUnitId) => {
  if (!businessUnitId) return [];
  const { data } = await apiRequest(
    `/rbac/business-units/${businessUnitId}/departments`,
    {
      method: "GET",
    },
  );
  return Array.isArray(data?.departments) ? data.departments : [];
};

export const setDepartmentForUser = async (userId, departmentId) => {
  const { data } = await apiRequest("/rbac/users/set-department", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      department_id: departmentId,
    }),
  });
  return data;
};
