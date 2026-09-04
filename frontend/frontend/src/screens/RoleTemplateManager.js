// Role Template Management - Unified RBAC Interface
// Single screen: Left panel (role list) + Right panel (permissions matrix)
// One resource = One row with 4 action checkboxes (V/C/E/D)

import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Plus, Edit2, Trash2, Copy, ChevronDown, ChevronRight, Search, AlertCircle, CheckCircle2
} from "lucide-react";
import { Card, Button, Input, Modal } from "../components/ui";
import { toast } from "react-toastify";
import { roleTemplatesAPI } from "../services/api/roleTemplates";
import { apiRequest } from "../services/api/client";

// Utility function to group resources by module
const groupResourcesByModule = (permissions) => {
  const grouped = {};
  permissions.forEach(perm => {
    if (!perm.module_id) return;
    const moduleName = perm.module_display || `Module ${perm.module_id}`;
    if (!grouped[moduleName]) {
      grouped[moduleName] = {
        module_id: perm.module_id,
        resources: []
      };
    }
    grouped[moduleName].resources.push(perm);
  });
  return grouped;
};

function RoleListPanel({ roles, selectedRoleId, onRoleSelect, onAddRole, onCloneRole, onDeleteRole }) {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDisplay, setNewRoleDisplay] = useState("");

  const handleCreate = async () => {
    if (!newRoleName.trim()) {
      toast.error("Role name is required");
      return;
    }
    try {
      await apiRequest("/admin/role-templates", {
        method: "POST",
        body: JSON.stringify({
          name: newRoleName,
          display_name: newRoleDisplay || newRoleName,
          description: "",
          permissions: []
        })
      });
      toast.success("Role created successfully");
      setIsCreateModalOpen(false);
      setNewRoleName("");
      setNewRoleDisplay("");
      onAddRole();
    } catch (error) {
      toast.error(`Failed to create role: ${error.message}`);
    }
  };

  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Roles</h2>
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          size="sm"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Role
        </Button>
      </div>

      {/* Role List */}
      <div className="flex-1 overflow-y-auto">
        {roles.map(role => (
          <div
            key={role.id}
            onClick={() => onRoleSelect(role.id)}
            className={`px-4 py-3 border-l-4 cursor-pointer transition ${
              selectedRoleId === role.id
                ? "bg-blue-50 border-blue-600"
                : "bg-white border-transparent hover:bg-gray-100"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm text-gray-900 truncate">{role.display_name}</p>
                <p className="text-xs text-gray-500 truncate">{role.name}</p>
                {role.is_system && (
                  <span className="inline-block mt-1 px-2 py-0.5 bg-gray-200 text-gray-700 text-xs rounded">
                    System
                  </span>
                )}
              </div>
              {selectedRoleId === role.id && (
                <div className="flex gap-1 flex-shrink-0">
                  {!role.is_system && (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onCloneRole(role.id);
                        }}
                        className="p-1 text-gray-500 hover:text-gray-700"
                        title="Clone role"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm("Delete this role?")) onDeleteRole(role.id);
                        }}
                        className="p-1 text-red-500 hover:text-red-700"
                        title="Delete role"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create Role Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 w-96 shadow-lg">
            <h3 className="text-lg font-semibold mb-4">Create New Role</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Role Name (identifier)
                </label>
                <Input
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="e.g., recruiter, hr_manager"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Display Name
                </label>
                <Input
                  value={newRoleDisplay}
                  onChange={(e) => setNewRoleDisplay(e.target.value)}
                  placeholder="e.g., Recruiter"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <Button
                onClick={() => setIsCreateModalOpen(false)}
                variant="outline"
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
              >
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PermissionsMatrixPanel({ role, allModules, onPermissionChange, onRefresh, isSaving }) {
  const [expandedModules, setExpandedModules] = useState({});
  const [searchQuery, setSearchQuery] = useState("");
  const [filteredModules, setFilteredModules] = useState({});

  // Filter resources based on search query
  useEffect(() => {
    if (!allModules || Object.keys(allModules).length === 0) return;

    if (!searchQuery.trim()) {
      setFilteredModules(allModules);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = {};

    Object.entries(allModules).forEach(([moduleName, moduleData]) => {
      const matchedResources = moduleData.resources.filter(resource =>
        resource.resource_display?.toLowerCase().includes(query) ||
        resource.resource_name?.toLowerCase().includes(query)
      );

      if (matchedResources.length > 0) {
        filtered[moduleName] = {
          ...moduleData,
          resources: matchedResources
        };
      }
    });

    setFilteredModules(filtered);
  }, [searchQuery, allModules]);

  // Auto-expand modules when searching
  useEffect(() => {
    if (searchQuery.trim()) {
      const newExpanded = {};
      Object.keys(filteredModules).forEach(module => {
        newExpanded[module] = true;
      });
      setExpandedModules(newExpanded);
    }
  }, [searchQuery, filteredModules]);

  const toggleModule = (moduleName) => {
    setExpandedModules(prev => ({
      ...prev,
      [moduleName]: !prev[moduleName]
    }));
  };

  const toggleExpandAll = () => {
    const allExpanded = Object.keys(filteredModules).every(m => expandedModules[m]);
    const newExpanded = {};
    Object.keys(filteredModules).forEach(module => {
      newExpanded[module] = !allExpanded;
    });
    setExpandedModules(newExpanded);
  };

  const handlePermissionToggle = (resourceId, action) => {
    onPermissionChange(resourceId, action);
  };

  const handleSelectAllInModule = (moduleName, moduleData, allChecked) => {
    moduleData.resources.forEach(resource => {
      const actions = ["can_view", "can_create", "can_edit", "can_delete"];
      actions.forEach(action => {
        const currentValue = resource[action] || false;
        if (currentValue !== !allChecked) {
          handlePermissionToggle(resource.resource_id, action);
        }
      });
    });
  };

  if (!role) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Select a role to manage permissions</p>
      </div>
    );
  }

  const isSuperUser = role.name?.toLowerCase() === "super_user" || role.name?.toLowerCase() === "superuser";

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{role.display_name}</h2>
            <p className="text-sm text-gray-600 mt-1">{role.description || "No description"}</p>
            {isSuperUser && (
              <div className="flex items-center gap-2 mt-2 text-blue-600">
                <CheckCircle2 className="w-4 h-4" />
                <span className="text-sm font-medium">All permissions (locked for Super User)</span>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              onClick={onRefresh}
              variant="outline"
              disabled={isSaving}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search resources..."
            className="pl-10"
          />
        </div>
      </div>

      {/* Warning for removing Super User permissions */}
      {isSuperUser && (
        <div className="mx-6 mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex gap-2">
          <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          <p className="text-sm text-yellow-800">
            Super User has all permissions. These cannot be modified.
          </p>
        </div>
      )}

      {/* Expand All Toggle */}
      <div className="px-6 pt-4 pb-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={Object.keys(filteredModules).every(m => expandedModules[m])}
            onChange={toggleExpandAll}
            className="w-4 h-4 rounded"
          />
          <span className="text-sm font-medium text-gray-700">
            {Object.keys(filteredModules).every(m => expandedModules[m]) ? "Collapse all" : "Expand all"}
          </span>
        </label>
      </div>

      {/* Permissions Matrix */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="space-y-4">
          {Object.entries(filteredModules).map(([moduleName, moduleData]) => (
            <div key={moduleName} className="border border-gray-200 rounded-lg">
              {/* Module Header */}
              <button
                onClick={() => toggleModule(moduleName)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition"
              >
                <div className="flex items-center gap-2">
                  {expandedModules[moduleName] ? (
                    <ChevronDown className="w-4 h-4 text-gray-600" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-600" />
                  )}
                  <h3 className="font-semibold text-gray-900">{moduleName}</h3>
                  <span className="text-xs text-gray-500">
                    ({moduleData.resources.length})
                  </span>
                </div>
              </button>

              {/* Module Content */}
              {expandedModules[moduleName] && (
                <div className="border-t border-gray-100 bg-gray-50">
                  {/* Table Header */}
                  <div className="grid grid-cols-12 gap-0 px-4 py-2 text-xs font-semibold text-gray-600 bg-gray-100 border-b">
                    <div className="col-span-4">Resource</div>
                    <div className="col-span-2 text-center">View</div>
                    <div className="col-span-2 text-center">Create</div>
                    <div className="col-span-2 text-center">Edit</div>
                    <div className="col-span-2 text-center">Delete</div>
                  </div>

                  {/* Resources */}
                  {moduleData.resources.map((resource, idx) => (
                    <div
                      key={resource.resource_id}
                      className={`grid grid-cols-12 gap-0 px-4 py-3 items-center border-b last:border-b-0 ${
                        idx % 2 === 0 ? "bg-white" : "bg-gray-50"
                      }`}
                    >
                      <div className="col-span-4">
                        <p className="font-medium text-gray-900">{resource.resource_display}</p>
                        <p className="text-xs text-gray-500">{resource.resource_name}</p>
                      </div>

                      {/* V/C/E/D Checkboxes */}
                      {["can_view", "can_create", "can_edit", "can_delete"].map((action, idx) => (
                        <div key={action} className="col-span-2 flex justify-center">
                          <input
                            type="checkbox"
                            checked={resource[action] || false}
                            onChange={() => handlePermissionToggle(resource.resource_id, action)}
                            disabled={isSuperUser || isSaving}
                            className="w-4 h-4 rounded cursor-pointer"
                          />
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {Object.keys(filteredModules).length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No resources match your search</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RoleTemplateManager() {
  const [roles, setRoles] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  const [allModules, setAllModules] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Load roles and modules
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [rolesRes, modulesRes] = await Promise.all([
        roleTemplatesAPI.listTemplates(),
        apiRequest("/admin/modules")
      ]);

      const rolesList = rolesRes.role_templates || [];
      setRoles(rolesList);

      if (rolesList.length > 0 && !selectedRoleId) {
        setSelectedRoleId(rolesList[0].id);
      }

      // Transform modules data to match permissions matrix structure
      const modulesData = modulesRes.modules || [];
      const grouped = {};

      modulesData.forEach(module => {
        const moduleName = module.display_name;
        grouped[moduleName] = {
          module_id: module.id,
          resources: module.resources.map(res => ({
            resource_id: res.id,
            resource_name: res.name,
            resource_display: res.display_name,
            module_display: moduleName,
            can_view: false,
            can_create: false,
            can_edit: false,
            can_delete: false
          }))
        };
      });

      setAllModules(grouped);
    } catch (error) {
      toast.error(`Failed to load data: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }, [selectedRoleId]);

  // Load selected role permissions
  const loadRolePermissions = useCallback(async (roleId) => {
    try {
      const roleData = await roleTemplatesAPI.getTemplate(roleId);
      setSelectedRole(roleData);

      // Update allModules with permission data from selected role
      const updatedModules = JSON.parse(JSON.stringify(allModules));
      const permissions = roleData.permissions || [];

      permissions.forEach(perm => {
        Object.values(updatedModules).forEach(module => {
          const resource = module.resources.find(r => r.resource_id === perm.resource_id);
          if (resource) {
            resource.can_view = perm.can_view;
            resource.can_create = perm.can_create;
            resource.can_edit = perm.can_edit;
            resource.can_delete = perm.can_delete;
          }
        });
      });

      setAllModules(updatedModules);
    } catch (error) {
      toast.error(`Failed to load role: ${error.message}`);
    }
  }, [allModules]);

  // Initial load
  useEffect(() => {
    loadData();
  }, []);

  // Load role when selected
  useEffect(() => {
    if (selectedRoleId) {
      loadRolePermissions(selectedRoleId);
    }
  }, [selectedRoleId, loadRolePermissions]);

  const handlePermissionChange = useCallback(async (resourceId, action) => {
    if (saving) return;

    setSaving(true);
    try {
      // Optimistically update UI
      const updatedModules = JSON.parse(JSON.stringify(allModules));
      Object.values(updatedModules).forEach(module => {
        module.resources.forEach(resource => {
          if (resource.resource_id === resourceId) {
            resource[action] = !resource[action];
          }
        });
      });
      setAllModules(updatedModules);

      // Send to backend
      const permissions = [];
      Object.values(updatedModules).forEach(module => {
        module.resources.forEach(resource => {
          permissions.push({
            resource_id: resource.resource_id,
            can_view: resource.can_view,
            can_create: resource.can_create,
            can_edit: resource.can_edit,
            can_delete: resource.can_delete
          });
        });
      });

      await roleTemplatesAPI.updateTemplate(selectedRoleId, { permissions });
      toast.success("Permission updated");
    } catch (error) {
      toast.error(`Failed to update permission: ${error.message}`);
      loadRolePermissions(selectedRoleId);
    } finally {
      setSaving(false);
    }
  }, [selectedRoleId, allModules, saving, loadRolePermissions]);

  const handleCloneRole = async (roleId) => {
    const roleToClone = roles.find(r => r.id === roleId);
    if (!roleToClone) return;

    const newName = `${roleToClone.name}_copy`;
    try {
      const result = await roleTemplatesAPI.createTemplate({
        name: newName,
        display_name: `${roleToClone.display_name} (Copy)`,
        description: roleToClone.description,
        permissions: roleToClone.permissions || []
      });
      toast.success("Role cloned successfully");
      await loadData();
    } catch (error) {
      toast.error(`Failed to clone role: ${error.message}`);
    }
  };

  const handleDeleteRole = async (roleId) => {
    try {
      await roleTemplatesAPI.deleteTemplate(roleId);
      toast.success("Role deleted successfully");
      if (selectedRoleId === roleId) {
        setSelectedRoleId(null);
      }
      await loadData();
    } catch (error) {
      toast.error(`Failed to delete role: ${error.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading role templates...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-white">
      <RoleListPanel
        roles={roles}
        selectedRoleId={selectedRoleId}
        onRoleSelect={setSelectedRoleId}
        onAddRole={loadData}
        onCloneRole={handleCloneRole}
        onDeleteRole={handleDeleteRole}
      />
      <PermissionsMatrixPanel
        role={selectedRole}
        allModules={allModules}
        onPermissionChange={handlePermissionChange}
        onRefresh={() => loadRolePermissions(selectedRoleId)}
        isSaving={saving}
      />
    </div>
  );
}
