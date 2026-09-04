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

export const createRoleTemplate = async (payload) => {
  const { data } = await apiRequest("/admin/role-templates", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      display_name: payload.display_name || payload.name,
      description: payload.description || null,
      permissions: payload.permissions || [],
    }),
  });
  return data;
};

export const updateRoleTemplate = async (templateId, payload) => {
  const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify({
      display_name: payload.display_name,
      description: payload.description || null,
      permissions: payload.permissions || [],
    }),
  });
  return data;
};

export const deleteRoleTemplate = async (templateId) => {
  await apiRequest(`/admin/role-templates/${templateId}`, { method: "DELETE" });
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

export const getModuleResources = async (moduleName) => {
  const { data } = await apiRequest(`/admin/modules/${moduleName}/resources`, { method: "GET" });
  return data?.resources || [];
};

// Update role template permissions (full replace)
export const updateRoleTemplatePermissions = async (templateId, payload) => {
  const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

// Grant permission to role template
export const grantPermission = async (templateId, resourceId, action) => {
  try {
    // Get current template with permissions
    const template = await getRoleTemplate(templateId);

    // Find or create the permission for this resource
    const existingPerm = template.permissions?.find(p => p.resource_id === resourceId);
    const updatedPerms = template.permissions || [];

    if (existingPerm) {
      // Update existing permission
      const permIndex = updatedPerms.findIndex(p => p.resource_id === resourceId);
      updatedPerms[permIndex] = {
        ...existingPerm,
        [action === 'view' ? 'can_view' : `can_${action}`]: true
      };
    } else {
      // Create new permission
      updatedPerms.push({
        resource_id: resourceId,
        can_view: action === 'view',
        can_create: action === 'create',
        can_edit: action === 'edit',
        can_delete: action === 'delete'
      });
    }

    return updateRoleTemplatePermissions(templateId, {
      display_name: template.display_name,
      description: template.description,
      permissions: updatedPerms
    });
  } catch (err) {
    throw new Error(`Failed to grant permission: ${err.message}`);
  }
};

// Revoke permission from role template
export const revokePermission = async (templateId, resourceId, action) => {
  try {
    // Get current template with permissions
    const template = await getRoleTemplate(templateId);

    const updatedPerms = (template.permissions || []).map(p => {
      if (p.resource_id === resourceId) {
        return {
          ...p,
          [action === 'view' ? 'can_view' : `can_${action}`]: false
        };
      }
      return p;
    });

    return updateRoleTemplatePermissions(templateId, {
      display_name: template.display_name,
      description: template.description,
      permissions: updatedPerms
    });
  } catch (err) {
    throw new Error(`Failed to revoke permission: ${err.message}`);
  }
};
