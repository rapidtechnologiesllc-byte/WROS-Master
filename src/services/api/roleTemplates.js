import { apiRequest } from './apiRequest';

export const roleTemplatesAPI = {
  // List all role templates
  listTemplates: () =>
    apiRequest('/admin/role-templates', { method: 'GET' }),

  // Get single template
  getTemplate: (templateId) =>
    apiRequest(`/admin/role-templates/${templateId}`, { method: 'GET' }),

  // Create new template
  createTemplate: (data) =>
    apiRequest('/admin/role-templates', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update template
  updateTemplate: (templateId, data) =>
    apiRequest(`/admin/role-templates/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete template
  deleteTemplate: (templateId) =>
    apiRequest(`/admin/role-templates/${templateId}`, { method: 'DELETE' }),

  // Grant permission
  grantPermission: (templateId, data) =>
    apiRequest(`/admin/role-templates/${templateId}/grant-permission`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Revoke permission
  revokePermission: (templateId, data) =>
    apiRequest(`/admin/role-templates/${templateId}/revoke-permission`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Get audit trail
  getAuditTrail: (templateId) =>
    apiRequest(`/admin/role-templates/${templateId}/audit-trail`, { method: 'GET' }),

  // Query audit logs
  getAuditLogs: (entityType, action, limit = 100) => {
    let url = '/admin/role-templates/audit/logs?';
    if (entityType) url += `entity_type=${entityType}&`;
    if (action) url += `action=${action}&`;
    url += `limit=${limit}`;
    return apiRequest(url, { method: 'GET' });
  },

  // Permission composition endpoints
  expandPermissions: (templateId, userAttributes = null) =>
    apiRequest('/admin/permissions/expand', {
      method: 'POST',
      body: JSON.stringify({
        role_template_id: templateId,
        user_attributes: userAttributes,
      }),
    }),

  checkPermission: (templateId, permission) =>
    apiRequest('/admin/permissions/check', {
      method: 'POST',
      body: JSON.stringify({
        role_template_id: templateId,
        required_permission: permission,
      }),
    }),

  validatePermissions: (permissions) =>
    apiRequest('/admin/permissions/validate', {
      method: 'POST',
      body: JSON.stringify({ permissions }),
    }),

  getPermissionTree: (templateId) =>
    apiRequest(`/admin/permissions/${templateId}/tree`, { method: 'GET' }),

  getPermissionHierarchyRules: () =>
    apiRequest('/admin/permissions/hierarchy/rules', { method: 'GET' }),

  // Get business units
  getBusinessUnits: () =>
    apiRequest('/rbac/business-units', { method: 'GET' }),
};
