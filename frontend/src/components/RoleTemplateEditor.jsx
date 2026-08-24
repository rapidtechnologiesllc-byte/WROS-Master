import React, { useState, useEffect } from 'react';
import { Input, Button } from './ui';
import { toast } from 'react-toastify';
import { apiRequest } from '../services/api/client';

const RoleTemplateEditor = ({ mode = 'create', templateId = null, onClose, onSuccess, modules }) => {
  const [loading, setLoading] = useState(mode === 'edit');
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: ''
  });
  const [permissions, setPermissions] = useState({});
  const [expandedModules, setExpandedModules] = useState({});

  // Load template data when editing
  useEffect(() => {
    if (mode === 'edit' && templateId) {
      const fetchTemplate = async () => {
        try {
          const { data } = await apiRequest(`/admin/role-templates/${templateId}`, {
            method: 'GET'
          });

          setFormData({
            name: data.name || '',
            description: data.description || ''
          });

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
          console.error('Failed to load template:', err);
          toast.error('Failed to load template data');
        } finally {
          setLoading(false);
        }
      };

      fetchTemplate();
    }
  }, [mode, templateId]);

  const handleTogglePermission = (resourceName, action) => {
    setPermissions(prev => ({
      ...prev,
      [resourceName]: {
        ...prev[resourceName],
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
        toast.error(`${moduleName}: You opened this module but didn't enable any permissions. Add at least one permission or close it.`);
        return; // Don't close the module
      }

      // Valid close - disable all permissions
      const newPerms = { ...permissions };
      resources.forEach(resource => {
        const resName = resource.name || resource.resource_name;
        ['view', 'create', 'edit', 'delete'].forEach(action => {
          newPerms[resName][action] = false;
        });
      });
      setPermissions(newPerms);
    }
    // If enable=true, just expand module - user must add at least one permission to close it
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
      toast.error('Template name is required');
      return;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        // Check if template name already exists (preventing duplicates)
        try {
          await apiRequest(`/admin/role-templates?search=${encodeURIComponent(formData.name)}`, {
            method: 'GET'
          });
          // If we got here, check if name already exists
          const checkResponse = await apiRequest(`/admin/role-templates`, {
            method: 'GET'
          });

          if (Array.isArray(checkResponse.data)) {
            const duplicate = checkResponse.data.find(t => t.name?.toLowerCase() === formData.name.toLowerCase());
            if (duplicate) {
              toast.error(`A role template named "${formData.name}" already exists. Please use a different name.`);
              setSaving(false);
              return;
            }
          }
        } catch (err) {
          // If search fails, continue with creation (endpoint may not support search)
        }

        const response = await apiRequest('/admin/role-templates', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.name,
            display_name: formData.name,
            description: formData.description,
            permissions: []
          })
        });

        // Store permissions after creating template
        const newTemplateId = response.data.id;
        await savePermissions(newTemplateId);

        toast.success('Role template created successfully');
        if (onSuccess) onSuccess(response.data);
        onClose();
      } else {
        await apiRequest(`/admin/role-templates/${templateId}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: formData.name,
            description: formData.description
          })
        });

        // Update permissions for existing template
        await savePermissions(templateId);

        toast.success('Role template updated successfully');
        if (onSuccess) onSuccess();
        onClose();
      }
    } catch (err) {
      toast.error(err.message || `Failed to ${mode === 'create' ? 'create' : 'update'} template`);
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
          console.error(`Failed to ${enabled ? 'grant' : 'revoke'} ${resourceName} ${action}:`, err);
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
              {mode === 'create' ? 'Create New Role Template' : 'Edit Role Template'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Configure permissions for this role template
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Form Content */}
        <div className="p-6 space-y-6">
          {/* Template Details */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-900">Template Details</h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Template Name *
              </label>
              <Input
                type="text"
                value={formData.name}
                onChange={(val) => setFormData({ ...formData, name: val })}
                placeholder="e.g., Senior Recruiter"
                disabled={mode === 'edit'}
                className={mode === 'edit' ? 'bg-gray-100' : ''}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe what this role template is for..."
                rows="3"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                          {/* Toggle ON/OFF - doesn't auto-enable, just expands module */}
                          <button
                            onClick={() => {
                              setExpandedModules(prev => ({
                                ...prev,
                                [moduleName]: enabledCount > 0 ? !prev[moduleName] : true
                              }));
                              handleToggleModule(moduleName, resources, enabledCount > 0 ? false : true);
                            }}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              enabledCount === totalPossible && totalPossible > 0
                                ? 'bg-green-500'
                                : enabledCount > 0
                                ? 'bg-amber-400'
                                : 'bg-red-500'
                            }`}
                            title={enabledCount > 0 ? 'Disable module' : 'Enable module'}
                          >
                            <span
                              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                enabledCount === totalPossible && totalPossible > 0
                                  ? 'translate-x-6'
                                  : enabledCount > 0
                                  ? 'translate-x-4'
                                  : 'translate-x-1'
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
