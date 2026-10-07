// Role Template API wrappers - New system (replaces old RBAC)
import { apiRequest } from "./client";

// Role Templates
export const listRoleTemplates = async () => {
  const { data } = await apiRequest("/admin/role-templates", { method: "GET" });
  return data?.role_templates || [];
};

export const getRoleTemplate = async (templateId) => {
  const { data } = await apiRequest(`/admin/role-templates/${templateId}`, { method: "GET" });
  return data;
};







// Modules and Resources
export const listModulesAndResources = async () => {
  try {
    const { data } = await apiRequest("/admin/modules", { method: "GET" });
    // Backend already returns resources for each module
    // Response format: { modules: [{ id, name, resources: [...] }, ...] }
    return data?.modules || [];
  } catch (err) {
    console.error("Failed to load modules:", err);
    return [];
  }
};



// Update role template permissions (full replace)
export const updateRoleTemplatePermissions = async (templateId, payload) => {
  const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

