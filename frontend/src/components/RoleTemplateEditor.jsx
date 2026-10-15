import React, { useState, useEffect } from 'react';
import { AlertCircle, CheckCircle, X } from 'lucide-react';
import { Input } from './ui';
import { apiRequest } from '../services/api/client';
import { hasPermission } from '../utils/permissionsRoleTemplate';

const RoleTemplateEditor = ({ mode = 'create', templateId = null, onClose, onSuccess, modules }) => {
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    specialization: 'General'
  });
  // A role's own permission set ({id, name, hierarchy_level}) vs a function add-on (null)
  const [ownerRole, setOwnerRole] = useState(null);
  const [functions, setFunctions] = useState(['General']);
  const [permissions, setPermissions] = useState({});
  const [expandedModules, setExpandedModules] = useState({});
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  // Permission Gate: Only users with role-templates.edit can access this component.
  // Evaluated before effects so no API calls fire for users without access.
  const canManageTemplates = hasPermission('role-templates', 'edit');

  useEffect(() => {
    if (!canManageTemplates) return;
    apiRequest('/admin/role-templates/functions', { method: 'GET' })
      .then(({ data }) => setFunctions(data.functions || ['General']))
      .catch((err) => {
        console.error('[RoleTemplateEditor] Failed to load functions:', err);
        setActionError(`Failed to load functions: ${err.message}`);
      });
  }, [canManageTemplates]);

  // Load template data when editing
  useEffect(() => {
    if (canManageTemplates && mode === 'edit' && templateId) {
      const fetchTemplate = async () => {
        try {
          const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
            method: 'GET'
          });

          setFormData({
            name: data.name || '',
            description: data.description || '',
            specialization: data.specialization || 'General'
          });
          setOwnerRole(data.owner_role || null);

          // Convert permissions to hierarchical structure
          const permsHierarchy = {};
          if (Array.isArray(data.permissions)) {
            data.permissions.forEach(perm => {
              if (perm.resource_id !== undefined) {
                const resourceName = perm.resource_name || `resource_${perm.resource_id}`;
                if (!permsHierarchy[resourceName]) {
                  permsHierarchy[resourceName] = {};
                }
                permsHierarchy[resourceName].view = perm.can_view || false;
                permsHierarchy[resourceName].create = perm.can_create || false;
                permsHierarchy[resourceName].edit = perm.can_edit || false;
                permsHierarchy[resourceName].delete = perm.can_delete || false;
              }
            });
          }
          setPermissions(permsHierarchy);
        } catch (err) {
          console.error('[RoleTemplateEditor] Failed to load template:', err);
          setActionError(`Failed to load template: ${err.message}`);
        } finally {
          setLoading(false);
        }
      };

      fetchTemplate();
    }
  }, [canManageTemplates, mode, templateId]);

  if (!canManageTemplates) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg p-6 max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">You do not have permission to manage role templates.</p>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const handleTogglePermission = (resourceName, action) => {
    setPermissions(prev => ({
      ...prev,
      [resourceName]: {
        view: prev[resourceName]?.view ?? false,
        create: prev[resourceName]?.create ?? false,
        edit: prev[resourceName]?.edit ?? false,
        delete: prev[resourceName]?.delete ?? false,
        [action]: !prev[resourceName]?.[action]
      }
    }));
  };

  const handleToggleModule = (moduleName, resources, enable) => {
    if (!enable) {
      // Turning OFF - check if user added any permissions first
      const enabledCount = resources.reduce((count, res) => {
        const resName = res.name || res.resource_name;
        const perms = permissions[resName] || {};
        return count + Object.values(perms).filter(Boolean).length;
      }, 0);

      // If they opened this module but didn't add any permissions, warn them
      if (enabledCount === 0) {
        setActionError(`${moduleName}: You opened this module but didn't enable any permissions. Add at least one permission or close it.`);
        return; // Don't close the module
      }

      // Valid close - disable all permissions
      const newPerms = { ...permissions };
      resources.forEach(resource => {
        const resName = resource.name || resource.resource_name;
        if (!newPerms[resName]) {
          newPerms[resName] = {};
        }
        ['view', 'create', 'edit', 'delete'].forEach(action => {
          newPerms[resName][action] = false;
        });
      });
      setPermissions(newPerms);
    }
  };

  const handleEnableAllForModule = (moduleName, resources) => {
    const newPerms = { ...permissions };
    resources.forEach(resource => {
      const resName = resource.name || resource.resource_name;
      if (!newPerms[resName]) {
        newPerms[resName] = {};
      }
      ['view', 'create', 'edit', 'delete'].forEach(action => {
        newPerms[resName][action] = true;
      });
    });
    setPermissions(newPerms);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setActionError('Template name is required');
      return;
    }

    // Require at least one permission to be enabled (only for create mode)
    if (mode === 'create') {
      const totalPermissions = Object.values(permissions).reduce((count, perms) => {
        return count + Object.values(perms).filter(Boolean).length;
      }, 0);

      if (totalPermissions === 0) {
        setActionError('Please enable at least one permission for this role template');
        return;
      }
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        const response = await apiRequest('/admin/role-templates', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.name,
            display_name: formData.name,
            description: formData.description,
            specialization: formData.specialization,
            permissions: []
          })
        });

        // Store permissions after creating template
        const newTemplateId = response.data.id;
        await savePermissions(newTemplateId);

        setActionSuccess('Role template created successfully');

        // Invalidate frontend permission cache so it refreshes on next login/navigation
        // Backend is source of truth; this ensures UI reflects latest permissions
        localStorage.removeItem('hrms_permissions');

        if (onSuccess) onSuccess(response.data);
        onClose();
      } else {
        await apiRequest(`/admin/role-templates/${templateId}`, {
          method: 'PUT',
          body: JSON.stringify({
            description: formData.description,
            ...(ownerRole ? {} : { specialization: formData.specialization }),
            permissions: []
          })
        });

        // Update permissions for existing template
        await savePermissions(templateId);

        setActionSuccess('Role template updated successfully');

        // Invalidate frontend permission cache so it refreshes on next login/navigation
        // Backend is source of truth; this ensures UI reflects latest permissions
        localStorage.removeItem('hrms_permissions');

        if (onSuccess) onSuccess();
        onClose();
      }
    } catch (err) {
      setActionError(err.message || `Failed to ${mode === 'create' ? 'create' : 'update'} template`);
    } finally {
      setSaving(false);
    }
  };

  const savePermissions = async (tId) => {
    // Get all resources from modules
    const allResources = {};
    if (Array.isArray(modules)) {
      modules.forEach(module => {
        const resources = module.resources || [];
        resources.forEach(resource => {
          const resName = resource.name || resource.resource_name;
          allResources[resName] = resource;
        });
      });
    }

    // Grant or revoke permissions
    for (const [resourceName, perms] of Object.entries(permissions)) {
      for (const [action, enabled] of Object.entries(perms)) {
        try {
          if (enabled) {
            await apiRequest(`/admin/role-templates/${tId}/grant-permission`, {
              method: 'POST',
              body: JSON.stringify({
                resource_name: resourceName,
                action: action
              })
            });
          } else {
            await apiRequest(`/admin/role-templates/${tId}/revoke-permission`, {
              method: 'POST',
              body: JSON.stringify({
                resource_name: resourceName,
                action: action
              })
            });
          }
        } catch (err) {
          const errorMsg = `Failed to ${enabled ? 'grant' : 'revoke'} ${resourceName} ${action}: ${err.message}`;
          console.error(errorMsg, err);
          throw new Error(errorMsg);
        }
      }
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md w-full">
          <p className="text-gray-600">Loading template...</p>
        </div>
      </div>
    );
  }

  // Get module list
  const moduleList = Array.isArray(modules) ? modules : [];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {mode === 'create' ? 'New function add-on' : ownerRole ? `${ownerRole.name} role permissions` : 'Edit function add-on'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {ownerRole ? "What everyone holding this role may see and do" : "Extra access on top of a person's role"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Action Error Banner */}
        {actionError && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-700 text-sm font-medium">{actionError}</p>
              </div>
              <button
                onClick={() => setActionError(null)}
                className="text-red-600 hover:text-red-800 flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Action Success Banner */}
        {actionSuccess && (
          <div className="mx-6 mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
              </div>
              <button
                onClick={() => setActionSuccess(null)}
                className="text-green-600 hover:text-green-800 flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Form Content */}
        <div className="p-6 space-y-6">
          {/* Template Details */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Template Details</h3>

            {ownerRole ? (
              <p className="text-sm bg-purple-50 border border-purple-200 text-purple-900 rounded-lg p-3">
                These are the permissions of the <strong>{ownerRole.name}</strong> role (L{ownerRole.hierarchy_level}).
                Everyone whose Job Title is {ownerRole.name} gets them, on top of their function add-on.
              </p>
            ) : (
              <p className="text-sm bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3">
                {mode === 'create' ? 'This creates a ' : 'This is a '}<strong>function add-on</strong>: extra access for
                people in one function (e.g. Recruitment), on top of their role. Each role already has its own
                permissions - edit those under Organizational Hierarchy → Manage Roles → Permissions.
              </p>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Template ID
              </label>
              <input
                type="text"
                value={mode === 'edit' ? templateId : 'Auto-generated'}
                disabled
                className="w-full rounded-lg bg-gray-100 dark:bg-gray-900 px-4 py-3 text-base font-semibold font-sans text-gray-600 dark:text-gray-400 outline-none cursor-not-allowed opacity-60"
                style={{ border: '1.5px solid #4b5563' }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Template Name *
              </label>
              <Input
                type="text"
                value={formData.name}
                onChange={(val) => setFormData({ ...formData, name: val })}
                placeholder="e.g., Recruitment access"
                disabled={mode === 'edit'}
                className={mode === 'edit' ? 'bg-gray-100' : ''}
              />
            </div>

            {!ownerRole && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Function *
                </label>
                <select
                  value={formData.specialization}
                  onChange={(e) => setFormData({ ...formData, specialization: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  {functions.map((f) => (
                    <option key={f} value={f}>{f === 'General' ? 'General (any function)' : f}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  People whose department is this function get this add-on suggested on the user form.
                </p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what this role template is for..."
                style={{
                  width: '100%',
                  padding: '8px 16px',
                  border: '1.5px solid #4b5563',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '600',
                  backgroundColor: 'white',
                  color: '#111827',
                  outline: 'none',
                  boxSizing: 'border-box',
                  fontFamily: 'system-ui, -apple-system, sans-serif'
                }}
              />
            </div>
          </div>

          {/* Permissions Grid */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Permissions</h3>
            <p className="text-sm text-gray-600">Select which resources this role can access and what actions they can perform</p>

            <div className="border rounded-lg divide-y max-h-[400px] overflow-y-auto">
              {moduleList.length > 0 ? (
                moduleList.map((module, idx) => {
                  const moduleName = typeof module === 'string' ? module : module.name;
                  const resources = module.resources || [];
                  const isExpanded = expandedModules[moduleName];

                  // Count enabled permissions for this module
                  const enabledCount = resources.reduce((count, res) => {
                    const resName = res.name || res.resource_name;
                    const perms = permissions[resName] || {};
                    return count + Object.values(perms).filter(Boolean).length;
                  }, 0);
                  const totalPossible = resources.length * 4;

                  return (
                    <div key={`module_${idx}`}>
                      {/* Module Header */}
                      <div className="bg-blue-50 px-4 py-3">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3 flex-1 cursor-pointer hover:opacity-70"
                            onClick={() => setExpandedModules(prev => ({
                              ...prev,
                              [moduleName]: !prev[moduleName]
                            }))}>
                            <span className="text-gray-600 text-lg">{isExpanded ? '▼' : '▶'}</span>
                            <div>
                              <h4 className="font-semibold text-gray-900 capitalize">{moduleName.replace(/_/g, ' ')}</h4>
                              <p className="text-xs text-gray-600">{enabledCount}/{totalPossible} permissions</p>
                            </div>
                          </div>
                          {/* Toggle button with proper color coding
                            Red: No permissions enabled
                            Amber/Yellow: Some permissions enabled (partial)
                            Green: All permissions enabled
                            Used to track state: checkbox status → permissions state → grant/revoke calls
                        */}
                          <button
                            onClick={() => {
                              setExpandedModules(prev => ({
                                ...prev,
                                [moduleName]: !prev[moduleName]
                              }));
                            }}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              enabledCount === 0
                                ? 'bg-red-500'
                                : enabledCount === totalPossible && totalPossible > 0
                                ? 'bg-green-500'
                                : 'bg-yellow-400'
                            }`}
                            title={`${enabledCount}/${totalPossible} permissions enabled`}
                          >
                            <span
                              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                enabledCount === 0
                                  ? 'translate-x-1'
                                  : enabledCount === totalPossible && totalPossible > 0
                                  ? 'translate-x-6'
                                  : 'translate-x-3'
                              }`}
                            />
                          </button>
                        </div>

                        {/* Quick Actions - Show when module has any permissions OR when expanded */}
                        {(enabledCount > 0 || isExpanded) && (
                          <div className="flex gap-2 pl-7">
                            <button
                              onClick={() => handleEnableAllForModule(moduleName, resources)}
                              className="text-xs px-3 py-1 bg-green-100 text-green-700 hover:bg-green-200 rounded font-medium transition"
                            >
                              Enable All
                            </button>
                            {enabledCount > 0 && enabledCount < totalPossible && (
                              <button
                                onClick={() => handleToggleModule(moduleName, resources, false)}
                                className="text-xs px-3 py-1 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded font-medium transition"
                              >
                                Disable All
                              </button>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Module Resources */}
                      {isExpanded && (
                        <div className="divide-y">
                          {resources.length > 0 ? (
                            resources.map(resource => {
                              const resName = resource.name || resource.resource_name;
                              const resDisplay = resource.display || resource.display_name || resName;
                              const perms = permissions[resName] || { view: false, create: false, edit: false, delete: false };

                              return (
                                <div key={`res_${resName}`} className="px-4 py-3 hover:bg-gray-50">
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium text-gray-900">{resDisplay}</span>
                                  </div>
                                  <div className="grid grid-cols-4 gap-2">
                                    {['view', 'create', 'edit', 'delete'].map(action => (
                                      <button
                                        key={action}
                                        onClick={() => handleTogglePermission(resName, action)}
                                        className={`py-1 px-2 rounded text-xs font-semibold transition ${
                                          perms[action]
                                            ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                            : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                                        }`}
                                        title={action.charAt(0).toUpperCase() + action.slice(1)}
                                      >
                                        {perms[action] ? '✓' : '○'} {action.charAt(0).toUpperCase()}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <div className="px-4 py-3 text-sm text-gray-500">No resources in this module</div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="px-4 py-6 text-center text-gray-500 text-sm">No modules available</div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 border-t px-6 py-4 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-bx-orange hover:bg-bx-orange-hover text-white rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : (mode === 'create' ? 'Create Template' : 'Save Changes')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoleTemplateEditor;
