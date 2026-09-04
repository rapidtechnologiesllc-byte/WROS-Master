import React, { useState, useEffect, useMemo } from 'react';
import { roleTemplatesAPI } from '../../services/api/roleTemplates';
import './PermissionMatrixEditor.css';

/**
 * PermissionMatrixEditor - Interactive matrix editor for all 175 resources
 * Displays resources grouped by module with V/C/E/D checkboxes
 * Allows real-time toggle and bulk save of permissions
 */
const PermissionMatrixEditor = ({ templateId, templateName, onSave, onCancel, loading }) => {
  const [resources, setResources] = useState([]);
  const [resourcesByModule, setResourcesByModule] = useState({});
  const [permissions, setPermissions] = useState({});
  const [changedPermissions, setChangedPermissions] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedModules, setExpandedModules] = useState(new Set());
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Load resources and current permissions
  useEffect(() => {
    loadResources();
  }, [templateId]);

  const loadResources = async () => {
    try {
      // Fetch all resources
      const resourcesResponse = await roleTemplatesAPI.getAllResources();
      const allResources = resourcesResponse.data.resources || [];

      setResources(allResources);

      // Group by module
      const grouped = {};
      allResources.forEach(resource => {
        if (!grouped[resource.module]) {
          grouped[resource.module] = [];
        }
        grouped[resource.module].push(resource);
      });

      setResourcesByModule(grouped);

      // Load current permissions for this template
      if (templateId) {
        const permsResponse = await roleTemplatesAPI.getTemplatePermissions(templateId);
        const permsMap = {};

        permsResponse.data.permissions?.forEach(perm => {
          const key = `${perm.resource_id}`;
          permsMap[key] = {
            view: perm.view_permission || false,
            create: perm.create_permission || false,
            edit: perm.edit_permission || false,
            delete: perm.delete_permission || false,
          };
        });

        setPermissions(permsMap);
      }

      // Auto-expand all modules initially
      setExpandedModules(new Set(Object.keys(grouped)));

      setError(null);
    } catch (err) {
      setError('Failed to load resources');
      console.error(err);
    }
  };

  // Handle permission toggle
  const togglePermission = (resourceId, action) => {
    const key = `${resourceId}`;
    const currentPerms = permissions[key] || { view: false, create: false, edit: false, delete: false };

    const newPerms = {
      ...currentPerms,
      [action]: !currentPerms[action],
    };

    setPermissions(prev => ({
      ...prev,
      [key]: newPerms,
    }));

    // Track changed permissions
    const changeKey = `${resourceId}-${action}`;
    const newChanged = new Set(changedPermissions);
    newChanged.add(changeKey);
    setChangedPermissions(newChanged);
  };

  // Handle bulk actions
  const setModulePermissions = (module, action, value) => {
    const newPerms = { ...permissions };
    const moduleResources = resourcesByModule[module] || [];

    moduleResources.forEach(resource => {
      const key = `${resource.id}`;
      if (!newPerms[key]) {
        newPerms[key] = { view: false, create: false, edit: false, delete: false };
      }
      newPerms[key][action] = value;

      const changeKey = `${resource.id}-${action}`;
      setChangedPermissions(prev => new Set(prev).add(changeKey));
    });

    setPermissions(newPerms);
  };

  // Filter resources by search
  const filteredModules = useMemo(() => {
    if (!searchTerm) {
      return resourcesByModule;
    }

    const filtered = {};
    Object.entries(resourcesByModule).forEach(([module, resources]) => {
      const moduleMatches = module.toLowerCase().includes(searchTerm.toLowerCase());
      const matchingResources = resources.filter(r =>
        r.resource_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        r.display_name?.toLowerCase().includes(searchTerm.toLowerCase())
      );

      if (moduleMatches || matchingResources.length > 0) {
        filtered[module] = matchingResources.length > 0 ? matchingResources : resources;
      }
    });

    return filtered;
  }, [resourcesByModule, searchTerm]);

  const handleSave = async () => {
    if (changedPermissions.size === 0) {
      setSuccessMessage('No changes to save');
      setTimeout(() => setSuccessMessage(null), 2000);
      return;
    }

    try {
      setSaving(true);

      // Convert permissions format for API
      const permissionsToSave = [];
      Object.entries(permissions).forEach(([resourceIdKey, perms]) => {
        permissionsToSave.push({
          resource_id: parseInt(resourceIdKey),
          view_permission: perms.view || false,
          create_permission: perms.create || false,
          edit_permission: perms.edit || false,
          delete_permission: perms.delete || false,
        });
      });

      if (templateId) {
        await roleTemplatesAPI.updateTemplatePermissions(templateId, {
          permissions: permissionsToSave,
        });
        setSuccessMessage(`Updated ${changedPermissions.size} permission(s)`);
      }

      setChangedPermissions(new Set());
      setTimeout(() => setSuccessMessage(null), 3000);

      if (onSave) {
        onSave();
      }
    } catch (err) {
      setError(err.message || 'Failed to save permissions');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const toggleModule = (module) => {
    const newExpanded = new Set(expandedModules);
    if (newExpanded.has(module)) {
      newExpanded.delete(module);
    } else {
      newExpanded.add(module);
    }
    setExpandedModules(newExpanded);
  };

  const totalResources = Object.values(filteredModules).reduce((sum, items) => sum + items.length, 0);
  const totalPermitted = Object.entries(permissions).filter(([, perms]) =>
    perms.view || perms.create || perms.edit || perms.delete
  ).length;

  return (
    <div className="permission-matrix-editor">
      {/* Header */}
      <div className="editor-header">
        <div className="header-title">
          <h3>Permission Matrix Editor</h3>
          <p className="subtitle">{templateName || 'New Template'}</p>
        </div>

        {/* Stats */}
        <div className="header-stats">
          <div className="stat">
            <span className="stat-value">{totalResources}</span>
            <span className="stat-label">Resources</span>
          </div>
          <div className="stat">
            <span className="stat-value">{totalPermitted}</span>
            <span className="stat-label">Permitted</span>
          </div>
          <div className="stat">
            <span className="stat-value">{changedPermissions.size}</span>
            <span className="stat-label">Changed</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && <div className="alert alert-error">{error}</div>}
      {successMessage && <div className="alert alert-success">{successMessage}</div>}

      {/* Search & Actions */}
      <div className="editor-toolbar">
        <input
          type="text"
          className="search-input"
          placeholder="Search resources by name or module..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <div className="toolbar-buttons">
          <button
            className="btn btn-secondary"
            onClick={() => setExpandedModules(new Set(Object.keys(filteredModules)))}
          >
            Expand All
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => setExpandedModules(new Set())}
          >
            Collapse All
          </button>
        </div>
      </div>

      {/* Matrix */}
      <div className="matrix-container">
        {Object.entries(filteredModules).map(([module, moduleResources]) => {
          const isExpanded = expandedModules.has(module);
          const modulePermCount = moduleResources.filter(r =>
            permissions[`${r.id}`]?.view ||
            permissions[`${r.id}`]?.create ||
            permissions[`${r.id}`]?.edit ||
            permissions[`${r.id}`]?.delete
          ).length;

          return (
            <div key={module} className="module-section">
              {/* Module Header */}
              <div
                className={`module-header ${isExpanded ? 'expanded' : ''}`}
                onClick={() => toggleModule(module)}
              >
                <span className="module-name">{module}</span>
                <span className="resource-count">{moduleResources.length} resources</span>
                <span className="permission-count">{modulePermCount} permitted</span>
                <span className={`expand-icon ${isExpanded ? 'rotated' : ''}`}>⊳</span>
              </div>

              {/* Module Bulk Actions */}
              {isExpanded && (
                <div className="module-bulk-actions">
                  <button
                    className="btn-small btn-small-primary"
                    onClick={() => setModulePermissions(module, 'view', true)}
                    title="Grant View to all resources in this module"
                  >
                    Grant All View
                  </button>
                  <button
                    className="btn-small btn-small-secondary"
                    onClick={() => setModulePermissions(module, 'view', false)}
                  >
                    Revoke All View
                  </button>
                  <button
                    className="btn-small btn-small-primary"
                    onClick={() => {
                      setModulePermissions(module, 'view', true);
                      setModulePermissions(module, 'create', true);
                      setModulePermissions(module, 'edit', true);
                      setModulePermissions(module, 'delete', true);
                    }}
                  >
                    Full Access
                  </button>
                  <button
                    className="btn-small btn-small-secondary"
                    onClick={() => {
                      setModulePermissions(module, 'view', false);
                      setModulePermissions(module, 'create', false);
                      setModulePermissions(module, 'edit', false);
                      setModulePermissions(module, 'delete', false);
                    }}
                  >
                    No Access
                  </button>
                </div>
              )}

              {/* Resources */}
              {isExpanded && (
                <div className="resources-list">
                  {moduleResources.map((resource) => {
                    const perms = permissions[`${resource.id}`] || { view: false, create: false, edit: false, delete: false };
                    const isLocked = templateName === 'Super User'; // Super User permissions locked

                    return (
                      <div key={resource.id} className="resource-row">
                        <div className="resource-info">
                          <div className="resource-name">{resource.display_name || resource.resource_name}</div>
                          <div className="resource-id">{resource.resource_name}</div>
                        </div>

                        <div className="permission-checkboxes">
                          <label className={`permission-label ${isLocked ? 'locked' : ''}`} title="View">
                            <input
                              type="checkbox"
                              checked={perms.view}
                              onChange={() => !isLocked && togglePermission(resource.id, 'view')}
                              disabled={isLocked}
                              className="permission-checkbox"
                            />
                            <span className="checkbox-icon">👁️</span>
                            <span className="checkbox-label">V</span>
                          </label>

                          <label className={`permission-label ${isLocked || !perms.view ? 'disabled' : ''}`} title="Create">
                            <input
                              type="checkbox"
                              checked={perms.create}
                              onChange={() => !isLocked && togglePermission(resource.id, 'create')}
                              disabled={isLocked}
                              className="permission-checkbox"
                            />
                            <span className="checkbox-icon">➕</span>
                            <span className="checkbox-label">C</span>
                          </label>

                          <label className={`permission-label ${isLocked || !perms.view ? 'disabled' : ''}`} title="Edit">
                            <input
                              type="checkbox"
                              checked={perms.edit}
                              onChange={() => !isLocked && togglePermission(resource.id, 'edit')}
                              disabled={isLocked}
                              className="permission-checkbox"
                            />
                            <span className="checkbox-icon">✏️</span>
                            <span className="checkbox-label">E</span>
                          </label>

                          <label className={`permission-label ${isLocked || !perms.view ? 'disabled' : ''}`} title="Delete">
                            <input
                              type="checkbox"
                              checked={perms.delete}
                              onChange={() => !isLocked && togglePermission(resource.id, 'delete')}
                              disabled={isLocked}
                              className="permission-checkbox"
                            />
                            <span className="checkbox-icon">🗑️</span>
                            <span className="checkbox-label">D</span>
                          </label>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Actions */}
      <div className="editor-footer">
        <div className="footer-info">
          {changedPermissions.size > 0 && (
            <span className="unsaved-changes">
              ⚠️ {changedPermissions.size} unsaved change(s)
            </span>
          )}
        </div>

        <div className="footer-buttons">
          <button
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || changedPermissions.size === 0}
          >
            {saving ? 'Saving...' : 'Save Permissions'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PermissionMatrixEditor;
