// RBAC API wrappers.
import { apiRequest } from "./client";


// Business units
export const listBusinessUnits = async () => {
  const { data } = await apiRequest("/rbac/business-units", { method: "GET" });
  // The endpoint wraps the list as { business_units: [...] }; callers expect the array.
  return Array.isArray(data) ? data : data?.business_units || [];
};


// Departments
export const listDepartments = async () => {
  // Departments live in the org structure API (/rbac/* does not exist)
  const { data } = await apiRequest("/org/departments", { method: "GET" });
  return data;
};


export const departmentList = async () => {
  const { data } = await apiRequest("/org/departments", { method: "GET" });
  return data;
};


// ---------------------------------------------------------------------
// Admin maintenance (roles/permissions/business-units/user assignments)
// ---------------------------------------------------------------------


// NEW: RBAC Matrix & Permission Grid Management (UI-focused endpoints)


