// Users & Access Control Management
// Nested route structure: /admin/users-access-control/:section
// Sections: users, business-units, delivery-centers, organizational-hierarchy, role-templates

import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Plus, Edit2, Trash2, Lock, Users, Building2, MapPin, Globe, AlertCircle, CheckCircle, X
} from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { canEdit, canDelete } from "../services/permissions";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import {
  getAllUsers,
  createHrUser,
  updateHrUser,
  deleteHrUser,
  updateUserPermissions,
  getUserPermissions
} from "../services/api/users";
import {
  listRoleTemplates,
  listModulesAndResources,
  grantPermission,
  revokePermission,
  getRoleTemplate
} from "../services/api/role_templates";
import { apiRequest } from "../services/api/client";
import { getHrMe } from "../services/api/users";
import RoleTemplateEditor from "../components/RoleTemplateEditor";

function SimpleModal({ isOpen, onClose, title, children }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function UserPermissionsModal({ isOpen, onClose, user, roles }) {
  const [expandedModules, setExpandedModules] = useState({});
  const [expandAll, setExpandAll] = useState(false);

  const userRole = roles.find(r => r.id === user?.role_id);
  const rolePermissions = userRole?.permissions || {};

  const moduleCategories = {
    "CRM": ["candidates", "contacts", "deals", "accounts"],
    "Recruitment": ["jobs", "interviews", "offers", "submissions"],
    "Project Management": ["projects", "allocations", "resources", "timesheet"],
    "Admin": ["role_templates", "users", "tenant_config", "locale", "ai_config"]
  };

  const toggleModule = (module) => {
    setExpandedModules(prev => ({
      ...prev,
      [module]: !prev[module]
    }));
  };

  const toggleExpandAll = () => {
    const newExpandAll = !expandAll;
    setExpandAll(newExpandAll);

    const newExpanded = {};
    Object.keys(moduleCategories).forEach(category => {
      newExpanded[category] = newExpandAll;
    });
    setExpandedModules(newExpanded);
  };

  if (!isOpen || !user) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-4xl max-h-[90vh] rounded-lg bg-white overflow-hidden flex flex-col">
        {/* Header */}
        <div className="border-b p-6 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Permissions for {user.user_name}</h2>
            <p className="text-sm text-gray-600">Role: {userRole?.name || 'No role assigned'}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-6">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={expandAll}
                onChange={toggleExpandAll}
                className="w-4 h-4"
              />
              <span className="text-sm font-medium text-gray-900">Expand all permissions</span>
            </label>
          </div>

          <div className="space-y-4">
            {Object.entries(moduleCategories).map(([category, modules]) => (
              <div key={category} className="border rounded-lg">
                <button
                  onClick={() => toggleModule(category)}
                  className="w-full px-4 py-3 flex items-center gap-2 hover:bg-gray-50 text-left"
                >
                  <span className={`transform transition ${expandedModules[category] ? 'rotate-180' : ''}`}>
                    ▼
                  </span>
                  <h3 className="font-semibold text-gray-900">{category}</h3>
                </button>

                {expandedModules[category] && (
                  <div className="border-t px-4 py-3 space-y-3 bg-gray-50">
                    {modules.map(module => {
                      const modulePerms = rolePermissions[module] || {};
                      const verbs = ["view", "create", "edit", "delete"];

                      return (
                        <div key={module} className="space-y-2">
                          <p className="text-sm font-medium text-gray-900 capitalize">{module.replace(/_/g, ' ')}</p>
                          <div className="flex flex-wrap gap-3 ml-4">
                            {verbs.map(verb => {
                              const hasPermission = modulePerms[verb] || false;
                              return (
                                <div key={verb} className="flex items-center gap-2">
                                  <span className="text-sm text-gray-600 capitalize">{verb}</span>
                                  <label className="flex items-center">
                                    <input
                                      type="checkbox"
                                      checked={hasPermission}
                                      disabled
                                      className="w-4 h-4"
                                    />
                                    <span className={`ml-1 text-xs font-semibold ${hasPermission ? 'text-green-600' : 'text-gray-400'}`}>
                                      {hasPermission ? '✓' : 'OFF'}
                                    </span>
                                  </label>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t p-6 flex gap-3 justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function safeText(v) {
  return v == null ? "" : String(v);
}

// USERS SECTION

function UsersSection({ loading, error, users, roles, currentUserPermissions = {}, employees = [] }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const [businessUnits, setBusinessUnits] = useState([]);

  const [partners, setPartners] = useState([
    { id: 1, name: "Partner 1" },
    { id: 2, name: "Partner 2" },
    { id: 3, name: "Partner 3" }
  ]);

  const [jobTitles, setJobTitles] = useState([]);

  const ORG_LEVEL_ROLES = ["CEO", "CFO", "Admin", "Finance"]; // No BU restriction

  const [resetForm, setResetForm] = useState({
    new_password: ""
  });


  const filteredUsers = useMemo(() => {
    if (!Array.isArray(users)) return [];
    if (!searchTerm) return users;
    const term = searchTerm.toLowerCase();
    return users.filter(u =>
      (u.user_name || "").toLowerCase().includes(term) ||
      (u.user_email || "").toLowerCase().includes(term)
    );
  }, [users, searchTerm]);


  const selectedUser = users.find(u => u.user_id === selectedUserId);

  const handleDelete = async () => {
    if (!selectedUserId) return;
    if (!window.confirm("Are you sure? This action cannot be undone.")) return;

    setActionError(null);
    setBusy(true);
    try {
      await deleteHrUser(selectedUserId);
      setActionSuccess("User deleted successfully.");
      setSelectedUserId("");
      window.location.reload();
    } catch (err) {
      setActionError(err.message || "Failed to delete user.");
    } finally {
      setBusy(false);
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUserId) return;
    if (!resetForm.new_password.trim()) {
      setActionError("New password is required.");
      return;
    }

    setActionError(null);
    setBusy(true);
    try {
      await apiRequest(`/hr/admin/users/${selectedUserId}/reset-password`, {
        method: "PUT",
        body: JSON.stringify({ new_password: resetForm.new_password })
      });
      setActionSuccess("Password reset successfully.");
      setShowResetModal(false);
      setResetForm({ new_password: "" });
      setSelectedUserId("");
    } catch (err) {
      setActionError(err.message || "Failed to reset password.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading users...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
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
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
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

      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Search users..."
          value={searchTerm}
          onChange={(val) => setSearchTerm(val)}
          className="max-w-xs"
        />
        {hasPermission("users", "edit") && (
          <Button
            onClick={() => navigate('/admin/users-access-control/users/create')}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            Add User
          </Button>
        )}
      </div>

      <Table
        columns={[
          { header: "Name", accessor: "user_name", key: "name" },
          { header: "Email", accessor: "user_email", key: "email" },
          { header: "Job Title", accessor: "job_title", key: "job_title" },
          { header: "Role Template", accessor: "permission_role", key: "role_template" },
          {
            header: "Actions",
            key: "actions",
            cell: (row) => (
              <div className="flex items-center gap-2">
                {canEdit(currentUserPermissions, "user") && (
                  <button
                    onClick={() => navigate(`/admin/users-access-control/users/${row.user_id}/edit`)}
                    className="text-blue-600 hover:text-blue-700"
                    title="Edit user and permissions"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelectedUserId(row.user_id);
                    setShowResetModal(true);
                  }}
                  className="text-amber-600 hover:text-amber-700"
                  title="Reset password"
                >
                  <Lock className="h-4 w-4" />
                </button>
                {canDelete(currentUserPermissions, "user") && (
                  <button
                    onClick={() => {
                      setSelectedUserId(row.user_id);
                      handleDelete();
                    }}
                    className="text-red-600 hover:text-red-700"
                    title="Delete user"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )
          }
        ]}
        data={filteredUsers}
      />
    </div>
  );
}


// ROLE TEMPLATES SECTION (showing all templates with their permissions)

function RoleTemplatesSection({ loading, error, modules, roles, setRoles, users }) {
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [toggling, setToggling] = useState({});
  const [togglingTemplate, setTogglingTemplate] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createRoleForm, setCreateRoleForm] = useState({ name: "", description: "" });
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [expandedModules, setExpandedModules] = useState({});
  const [moduleStates, setModuleStates] = useState({});
  const [createTemplatePermissions, setCreateTemplatePermissions] = useState({});
  const [createTemplateModuleStates, setCreateTemplateModuleStates] = useState({});
  const [createTemplateExpandedModules, setCreateTemplateExpandedModules] = useState({});
  const [showUsersModal, setShowUsersModal] = useState(false);
  const [selectedRoleForUsers, setSelectedRoleForUsers] = useState(null);
  const [roleUsers, setRoleUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Fetch template details when editingTemplateId changes
  useEffect(() => {
    if (editingTemplateId) {
      const fetchTemplate = async () => {
        try {
          const { data } = await apiRequest(`/admin/role-templates/${editingTemplateId}`, {
            method: "GET"
          });
          setEditingTemplate(data || { name: "New Template", description: "", permissions: [] });
        } catch (err) {
          console.error("Failed to fetch template:", err);
          setEditingTemplate({ name: "New Template", description: "", permissions: [] });
        }
      };
      fetchTemplate();
    } else {
      setEditingTemplate(null);
    }
  }, [editingTemplateId]);

  const filteredRoles = useMemo(() => {
    if (!searchTerm) return roles;
    const term = searchTerm.toLowerCase();
    return roles.filter(r =>
      (r.name || "").toLowerCase().includes(term) ||
      (r.description || "").toLowerCase().includes(term)
    );
  }, [roles, searchTerm]);

  // Count users per template - match by template name
  const getUserCount = (templateId, templateName) => {
    return users.filter(u => {
      // Match by user_role field (e.g., "Admin" matches template.name "Admin")
      if (u.user_role === templateName) return true;
      return false;
    }).length;
  };

  // Fetch users for a specific role template
  const handleShowUsers = async (roleId, roleName) => {
    setSelectedRoleForUsers({ id: roleId, name: roleName });
    setShowUsersModal(true);
    setLoadingUsers(true);

    try {
      const { data } = await apiRequest(`/admin/role-templates/${roleId}/users`, {
        method: "GET"
      });
      setRoleUsers(data.users || []);
    } catch (err) {
      console.error("Failed to fetch users:", err);
      setRoleUsers([]);
    } finally {
      setLoadingUsers(false);
    }
  };

  // Convert flat permission list to hierarchical structure { module: { verb: true } }
  const convertPermissionsToHierarchy = (perms) => {
    if (!Array.isArray(perms)) return {};

    const hierarchy = {};
    perms.forEach(perm => {
      if (!perm) return; // Skip null/undefined items

      // Handle new backend format: { resource_id, can_view, can_create, can_edit, can_delete }
      if (perm.resource_id !== undefined) {
        // Get resource name from the resource (need to look up resource name)
        // For now, use a placeholder - the actual resource name should come from backend
        const resourceName = perm.resource_name || `resource_${perm.resource_id}`;

        if (!hierarchy[resourceName]) {
          hierarchy[resourceName] = {};
        }
        hierarchy[resourceName].view = perm.can_view || false;
        hierarchy[resourceName].create = perm.can_create || false;
        hierarchy[resourceName].edit = perm.can_edit || false;
        hierarchy[resourceName].delete = perm.can_delete || false;
      }
      // Handle legacy format: { name: "candidates_view" }
      else if (perm.name) {
        const parts = perm.name.split('_');
        if (parts.length >= 2) {
          const verb = parts[parts.length - 1]; // Last part is the verb
          const module = parts.slice(0, -1).join('_'); // Everything else is the module

          if (!hierarchy[module]) {
            hierarchy[module] = {};
          }
          hierarchy[module][verb] = true;
        }
      }
    });
    return hierarchy;
  };

  const editingPermissions = convertPermissionsToHierarchy(editingTemplate?.permissions || []);

  const handleTogglePermission = async (resourceName, verb, currentState) => {
    if (!editingTemplateId) return;

    setActionError(null);
    const key = `${editingTemplateId}_${resourceName}_${verb}`;
    setToggling({ ...toggling, [key]: true });

    try {
      const newState = !currentState;

      // Call backend to update permission
      if (newState) {
        // Grant permission
        await apiRequest(`/admin/role-templates/${editingTemplateId}/grant-permission`, {
          method: "POST",
          body: JSON.stringify({
            resource_name: resourceName,
            action: verb
          })
        });
      } else {
        // Revoke permission
        await apiRequest(`/admin/role-templates/${editingTemplateId}/revoke-permission`, {
          method: "POST",
          body: JSON.stringify({
            resource_name: resourceName,
            action: verb
          })
        });
      }

      // Re-fetch the role template to get updated permissions from backend
      const updatedTemplate = await getRoleTemplate(editingTemplateId);

      // Update the roles array with the updated template
      setRoles(roles.map(r => r.id === editingTemplateId ? updatedTemplate : r));

      setActionSuccess(`Permission ${newState ? 'enabled' : 'disabled'} for ${resourceName} - ${verb}`);
    } catch (err) {
      setActionError(err.message || `Failed to update permission for ${resourceName}`);
    } finally {
      setToggling({ ...toggling, [key]: false });
    }
  };

  const handleToggleModule = async (moduleName, displayResources, shouldEnable) => {
    if (!editingTemplateId) return;

    setActionError(null);
    setToggling({ ...toggling, [moduleName]: true });

    try {
      // Toggle all permissions for all resources in the module
      for (const resource of displayResources) {
        const resName = resource.name || resource.resource_name;
        const actions = ['view', 'create', 'edit', 'delete'];

        for (const action of actions) {
          try {
            if (shouldEnable) {
              await apiRequest(`/admin/role-templates/${editingTemplateId}/grant-permission`, {
                method: "POST",
                body: JSON.stringify({
                  resource_name: resName,
                  action: action
                })
              });
            } else {
              await apiRequest(`/admin/role-templates/${editingTemplateId}/revoke-permission`, {
                method: "POST",
                body: JSON.stringify({
                  resource_name: resName,
                  action: action
                })
              });
            }
          } catch (err) {
            console.error(`Failed to ${shouldEnable ? 'enable' : 'disable'} ${resName} - ${action}:`, err);
          }
        }
      }

      // Re-fetch the role template to get updated permissions from backend
      const updatedTemplate = await getRoleTemplate(editingTemplateId);
      setRoles(roles.map(r => r.id === editingTemplateId ? updatedTemplate : r));

      setActionSuccess(`Module ${moduleName} ${shouldEnable ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      setActionError(err.message || `Failed to toggle module ${moduleName}`);
    } finally {
      setToggling({ ...toggling, [moduleName]: false });
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading templates...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  const handleCreateRole = async () => {
    setActionError(null);

    if (!createRoleForm.name.trim()) {
      setActionError("Role name is required.");
      return;
    }

    if (!canCreateTemplate()) {
      setActionError("Please enable at least one module and select permissions.");
      return;
    }

    setCreatingTemplate(true);
    try {
      await apiRequest("/admin/role-templates", {
        method: "POST",
        body: JSON.stringify({
          name: createRoleForm.name,
          display_name: createRoleForm.name,
          description: createRoleForm.description,
          permissions: createTemplatePermissions  // ✅ Use actual permissions
        })
      });
      setActionSuccess("Role created successfully.");
      setShowCreateModal(false);
      setCreateRoleForm({ name: "", description: "" });
      setCreateTemplatePermissions({});
      setCreateTemplateModuleStates({});
      window.location.reload();
    } catch (err) {
      setActionError(err.message || "Failed to create role.");
    } finally {
      setCreatingTemplate(false);
    }
  };

  const handleToggleTemplateStatus = async (templateId, currentStatus) => {
    setActionError(null);
    setTogglingTemplate({ ...togglingTemplate, [templateId]: true });

    try {
      // Call backend to toggle template active status
      await apiRequest(`/admin/role-templates/${templateId}/toggle-status`, {
        method: "POST",
        body: JSON.stringify({
          is_active: !currentStatus
        })
      });

      // Update the roles array with toggled status
      setRoles(roles.map(r =>
        r.id === templateId
          ? { ...r, enabled: !currentStatus }
          : r
      ));

      setActionSuccess(`Template ${!currentStatus ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      console.error("Failed to toggle template status:", err);
      setActionError(err.message || "Failed to toggle template status");
    } finally {
      setTogglingTemplate({ ...togglingTemplate, [templateId]: false });
    }
  };

  const handleNewRoleTemplate = () => {
    // Show modal to get template name/description from user
    setShowCreateModal(true);
    setCreateRoleForm({ name: "", description: "" });
    setCreateTemplatePermissions({});
    setCreateTemplateModuleStates({});
  };

  const handleCreateRoleToggleModule = (moduleName, resources, shouldEnable) => {
    setCreateTemplateModuleStates(prev => ({
      ...prev,
      [moduleName]: shouldEnable
    }));

    if (!shouldEnable) {
      // Clear permissions for this module when turning it off
      const newPerms = { ...createTemplatePermissions };
      resources.forEach(resource => {
        const resName = resource.name || resource.resource_name;
        delete newPerms[resName];
      });
      setCreateTemplatePermissions(newPerms);
    }
  };

  const handleCreateRoleTogglePermission = (resourceName, action, hasPermission) => {
    const newPerms = { ...createTemplatePermissions };
    if (!newPerms[resourceName]) {
      newPerms[resourceName] = { view: false, create: false, edit: false, delete: false };
    }
    newPerms[resourceName][action] = !hasPermission;
    setCreateTemplatePermissions(newPerms);
  };

  const canCreateTemplate = () => {
    // Check if at least one module is enabled
    const hasEnabledModule = Object.values(createTemplateModuleStates).some(enabled => enabled);
    // Check if at least one permission is selected
    const hasPermissions = Object.values(createTemplatePermissions).some(perms =>
      Object.values(perms).some(p => p)
    );
    return createRoleForm.name.trim() && hasEnabledModule && hasPermissions;
  };

  return (
    <div className="space-y-6">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
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
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
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

      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Search templates..."
          value={searchTerm}
          onChange={(val) => setSearchTerm(val)}
          className="max-w-xs"
        />
        <Button
          onClick={handleNewRoleTemplate}
          disabled={creatingTemplate}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          {creatingTemplate ? "Creating..." : "New role template"}
        </Button>
      </div>

      {/* Use RoleTemplateEditor for editing */}
      {editingTemplateId && (
        <RoleTemplateEditor
          mode="edit"
          templateId={editingTemplateId}
          onClose={() => setEditingTemplateId(null)}
          onSuccess={() => {
            setEditingTemplateId(null);
            window.location.reload();
          }}
          modules={modules}
        />
      )}

      {!editingTemplateId && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRoles.map(role => {
            const userCount = getUserCount(role.id, role.name);
            const isActive = role.enabled !== false; // Use enabled field from backend
            return (
              <div
                key={role.id}
                className={`border rounded-lg p-4 transition ${
                  isActive
                    ? 'bg-white hover:shadow-md'
                    : 'bg-gray-50 opacity-60'
                }`}
              >
                {/* Template Status Toggle */}
                <div className="flex items-center justify-between mb-3 pb-3 border-b">
                  <div className="flex-1">
                    <h3 className={`font-semibold ${isActive ? 'text-gray-900' : 'text-gray-500'}`}>
                      {role.name}
                    </h3>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleToggleTemplateStatus(role.id, isActive)}
                      disabled={togglingTemplate[role.id]}
                      className={`px-2 py-1 rounded text-xs font-semibold transition ${
                        isActive
                          ? 'bg-green-500 text-white hover:bg-green-600'
                          : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
                      }`}
                      title={isActive ? 'Click to disable' : 'Click to enable'}
                    >
                      {togglingTemplate[role.id] ? '...' : (isActive ? 'ON' : 'OFF')}
                    </button>
                  </div>
                </div>

                <p className={`text-xs ${isActive ? 'text-gray-600' : 'text-gray-500'} mb-3`}>
                  {role.description}
                </p>

                <div className="flex items-center justify-between">
                  <button
                    onClick={() => userCount > 0 && handleShowUsers(role.id, role.name)}
                    disabled={userCount === 0}
                    className={`text-xs font-medium transition ${
                      userCount > 0
                        ? 'text-blue-600 hover:text-blue-700 cursor-pointer'
                        : 'text-gray-400 cursor-not-allowed'
                    }`}
                    title={userCount > 0 ? 'Click to view users' : 'No users assigned'}
                  >
                    {userCount} user{userCount !== 1 ? 's' : ''}
                  </button>
                  <button
                    onClick={() => setEditingTemplateId(role.id)}
                    disabled={!isActive}
                    className={`text-sm font-medium transition ${
                      isActive
                        ? 'text-blue-600 hover:text-blue-700'
                        : 'text-gray-400 cursor-not-allowed'
                    }`}
                    title={isActive ? 'Edit permissions' : 'Enable template to edit'}
                  >
                    Edit Permissions
                  </button>
                </div>
              </div>
            );
          })}
          </div>
        </>
      )}

      {/* Use RoleTemplateEditor for creating */}
      {showCreateModal && (
        <RoleTemplateEditor
          mode="create"
          templateId={null}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            window.location.reload();
          }}
          modules={modules}
        />
      )}

      {/* Users Modal */}
      {showUsersModal && selectedRoleForUsers && (
        <SimpleModal
          isOpen={true}
          onClose={() => {
            setShowUsersModal(false);
            setSelectedRoleForUsers(null);
            setRoleUsers([]);
          }}
          title={`Users in "${selectedRoleForUsers.name}" Role`}
        >
          <div className="space-y-4">
            {loadingUsers ? (
              <div className="text-center py-8 text-gray-500">Loading users...</div>
            ) : roleUsers.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No users assigned to this role</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 border-b">
                    <tr>
                      <th className="px-4 py-2 text-left font-semibold">Name</th>
                      <th className="px-4 py-2 text-left font-semibold">Email</th>
                      <th className="px-4 py-2 text-left font-semibold">Business Unit</th>
                      <th className="px-4 py-2 text-left font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roleUsers.map(user => (
                      <tr key={user.user_id} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-2">{user.name}</td>
                        <td className="px-4 py-2">{user.email}</td>
                        <td className="px-4 py-2 text-gray-600">{user.business_unit || '-'}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            user.active !== false
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {user.active !== false ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </SimpleModal>
      )}
    </div>
  );
}

// MAIN COMPONENT

export default function UsersAndAccessControl() {
  const { section } = useParams();
  const navigate = useNavigate();

  // Map URL section to internal tab names
  const sectionMap = {
    "users": "users",
    "business-units": "business-units",
    "delivery-centers": "locations",  // Maps to LocationsSection (Delivery Centers)
    "organizational-hierarchy": "hierarchy",  // Maps to OrganizationalHierarchySection
    "role-templates": "templates"
  };

  // Get the current active tab from URL section, default to "users" if no section specified
  const activeTab = section ? sectionMap[section] : "users";

  // Validate that the section is valid, if not redirect to /admin/users-access-control/users
  useEffect(() => {
    if (section && !sectionMap[section]) {
      // Invalid section, redirect to default
      navigate("/admin/users-access-control/users");
    }
  }, [section, navigate]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [verbMatrix, setVerbMatrix] = useState({});
  const [currentUserPermissions, setCurrentUserPermissions] = useState({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      // Load users (required)
      const usersRes = await getAllUsers();
      setUsers(Array.isArray(usersRes) ? usersRes : []);

      // Load role templates (optional - may fail due to permissions)
      try {
        const rolesRes = await listRoleTemplates();
        setRoles(Array.isArray(rolesRes.role_templates || rolesRes) ? (rolesRes.role_templates || rolesRes) : []);
      } catch (rolesErr) {setRoles([]);
      }

      // Load modules/resources (optional - may fail due to permissions)
      let modulesRes = null;
      try {
        const modsRes = await listModulesAndResources();
        modulesRes = { modules: modsRes };
        setModules(modulesRes?.modules || []);
      } catch (modulesErr) {setModules([]);
      }

      // Fetch current user permissions
      try {
        const meData = await getHrMe();
        if (meData?.permissions) {
          setCurrentUserPermissions(meData.permissions);
        }
      } catch (permErr) {
      }

      // Convert verb_matrix from array-based to object-based structure
      // Input: { "candidates": ["view", "create"], "jobs": ["view", "edit"] }
      // Output: { "candidates": { "view": true, "create": true }, ... }
      const verbMatrixObj = {};
      const rawVerbMatrix = modulesRes?.verb_matrix || {};
      for (const [module, verbs] of Object.entries(rawVerbMatrix)) {
        verbMatrixObj[module] = {};
        if (Array.isArray(verbs)) {
          verbs.forEach(verb => {
            verbMatrixObj[module][verb] = true;
          });
        }
      }
      setVerbMatrix(verbMatrixObj);
    } catch (err) {
      setError(err.message || "Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

// BUSINESS UNITS SECTION (from AdminSettings)

function BusinessUnitsSection() {
  const navigate = useNavigate();
  const [businessUnits, setBusinessUnits] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  useEffect(() => {
    loadBusinessUnits();
  }, []);

  const loadBusinessUnits = async () => {
    try {
      const response = await apiRequest("/api/v1/business-units", {
        method: "GET"
      });
      const busData = Array.isArray(response) ? response : response?.data || [];
      setBusinessUnits(busData);
    } catch (err) {
      console.error("[BusinessUnitsSection] Failed to load business units:", err);
      setActionError(`Could not load business units: ${err.message}`);
    } finally {
      setLoaded(true);
    }
  };


  const handleDeleteBusinessUnit = async (buId) => {
    if (!window.confirm("Are you sure you want to delete this business unit?")) return;
    setActionError(null);
    try {
      await apiRequest(`/rbac/business-units/${buId}`, { method: "DELETE" });
      loadBusinessUnits();
      setActionSuccess("Business Unit deleted successfully");
    } catch (err) {
      setActionError("Failed to delete business unit");
    }
  };

  return (
    <div className="space-y-4">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
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
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
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

      {hasPermission("business-units", "create") && (
        <button
          onClick={() => navigate('/admin/users-access-control/business-units/create')}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Business Unit
        </button>
      )}
      {loaded && businessUnits.length === 0 && !actionError && (
        <p className="text-sm text-gray-600">No business units yet. Use Add Business Unit to create the first one.</p>
      )}
      <div className="space-y-3">
        {businessUnits.map((bu) => (
          <div key={bu.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
            <div className="flex-1">
              <h4 className="font-semibold text-gray-900">{bu.name}</h4>
              {bu.description && <p className="text-sm text-gray-600 mt-1">{bu.description}</p>}
              <div className="grid grid-cols-2 gap-4 mt-2 text-sm text-gray-600">
                <div><span className="font-medium">Region:</span> {bu.region || "-"}</div>
                <div><span className="font-medium">Continent:</span> {bu.continent || "-"}</div>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate(`/admin/users-access-control/business-units/${bu.id}/edit`)}
                className="p-2 text-blue-600 hover:bg-blue-50 rounded"
              >
                <Edit2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDeleteBusinessUnit(bu.id)}
                className="p-2 text-red-600 hover:bg-red-50 rounded"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ORGANIZATIONAL HIERARCHY SECTION

function OrganizationalHierarchySection() {
  const EMPTY_NODE_FORM = { name: "", hierarchy_level: "", specialization: "", parent_id: "", department_id: "" };

  const [orgNodes, setOrgNodes] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [reference, setReference] = useState({ levels: [], specializations: [] });
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const [showAddNode, setShowAddNode] = useState(false);
  const [nodeForm, setNodeForm] = useState(EMPTY_NODE_FORM);
  const [eligibleParents, setEligibleParents] = useState([]);
  const [submittingNode, setSubmittingNode] = useState(false);

  const [showDepartments, setShowDepartments] = useState(false);
  const [deptForm, setDeptForm] = useState({ name: "", business_unit_id: "" });
  const [editingDept, setEditingDept] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [nodesRes, deptRes, buRes, refRes] = await Promise.all([
        apiRequest("/org/nodes"),
        apiRequest("/org/departments"),
        apiRequest("/api/v1/business-units"),
        apiRequest("/org/hierarchy-reference"),
      ]);
      setOrgNodes(Array.isArray(nodesRes.data) ? nodesRes.data : []);
      setDepartments(Array.isArray(deptRes.data) ? deptRes.data : []);
      setBusinessUnits(Array.isArray(buRes.data) ? buRes.data : []);
      setReference(refRes.data || { levels: [], specializations: [] });
    } catch (err) {
      setActionError(err?.message || "Failed to load organizational hierarchy");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const levelName = (level) => reference.levels.find(l => l.level === level)?.name || `Level ${level}`;
  const departmentById = (id) => departments.find(d => d.id === id);

  // Eligible parents depend on level, specialization and the BU implied by the chosen department
  useEffect(() => {
    const level = Number(nodeForm.hierarchy_level);
    if (!showAddNode || !level || !nodeForm.specialization || level >= 17) {
      setEligibleParents([]);
      return;
    }
    const params = new URLSearchParams({ hierarchy_level: String(level), specialization: nodeForm.specialization });
    const dept = departmentById(nodeForm.department_id);
    if (dept) params.set("business_unit_id", String(dept.business_unit_id));
    apiRequest(`/org/valid-supervisors?${params.toString()}`)
      .then(res => setEligibleParents(Array.isArray(res.data) ? res.data : []))
      .catch(() => setEligibleParents([]));
  }, [showAddNode, nodeForm.hierarchy_level, nodeForm.specialization, nodeForm.department_id, departments]);

  const closeAddNode = () => {
    setShowAddNode(false);
    setNodeForm(EMPTY_NODE_FORM);
  };

  const handleAddNode = async (e) => {
    e.preventDefault();
    setActionError(null);
    setSubmittingNode(true);
    try {
      await apiRequest("/org/nodes", {
        method: "POST",
        body: JSON.stringify({
          name: nodeForm.name.trim(),
          hierarchy_level: Number(nodeForm.hierarchy_level),
          specialization: nodeForm.specialization,
          parent_id: nodeForm.parent_id || null,
          department_id: nodeForm.department_id || null,
        }),
      });
      setActionSuccess(`Added ${nodeForm.name.trim()} to the org chart`);
      closeAddNode();
      loadAll();
    } catch (err) {
      setActionError(err?.message || "Failed to create org node");
    } finally {
      setSubmittingNode(false);
    }
  };

  const handleDeleteNode = async (node) => {
    if (!window.confirm(`Remove ${node.name} from the org chart?`)) return;
    setActionError(null);
    try {
      await apiRequest(`/org/nodes/${node.id}`, { method: "DELETE" });
      setActionSuccess(`Removed ${node.name}`);
      loadAll();
    } catch (err) {
      setActionError(err?.message || "Failed to delete org node");
    }
  };

  const handleSaveDepartment = async (e) => {
    e.preventDefault();
    setActionError(null);
    const form = editingDept || deptForm;
    try {
      await apiRequest(editingDept ? `/org/departments/${editingDept.id}` : "/org/departments", {
        method: editingDept ? "PUT" : "POST",
        body: JSON.stringify({ name: form.name.trim(), business_unit_id: Number(form.business_unit_id) }),
      });
      setActionSuccess(editingDept ? "Department updated" : "Department added");
      setEditingDept(null);
      setDeptForm({ name: "", business_unit_id: "" });
      loadAll();
    } catch (err) {
      setActionError(err?.message || "Failed to save department");
    }
  };

  const handleDeleteDepartment = async (dept) => {
    if (!window.confirm(`Delete department ${dept.name}?`)) return;
    setActionError(null);
    try {
      await apiRequest(`/org/departments/${dept.id}`, { method: "DELETE" });
      setActionSuccess("Department deleted");
      loadAll();
    } catch (err) {
      setActionError(err?.message || "Failed to delete department");
    }
  };

  const childrenByParent = useMemo(() => {
    const ids = new Set(orgNodes.map(n => n.id));
    const map = { root: [] };
    orgNodes.forEach(n => {
      const key = n.parent_id && ids.has(n.parent_id) ? n.parent_id : "root";
      (map[key] = map[key] || []).push(n);
    });
    Object.values(map).forEach(list => list.sort((a, b) => b.hierarchy_level - a.hierarchy_level || a.name.localeCompare(b.name)));
    return map;
  }, [orgNodes]);

  const renderNode = (node, depth) => {
    const dept = departmentById(node.department_id);
    return (
      <div key={node.id}>
        <div
          className="flex items-center justify-between bg-white p-3 rounded border border-gray-200 hover:bg-gray-50"
          style={{ marginLeft: depth * 24 }}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-gray-900">{node.name}</h4>
            <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">
              L{node.hierarchy_level} · {levelName(node.hierarchy_level)}
            </span>
            <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded">{node.specialization}</span>
            {dept && (
              <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">
                {dept.name} · {dept.business_unit_name}
              </span>
            )}
          </div>
          <button
            onClick={() => handleDeleteNode(node)}
            className="p-2 text-red-600 hover:bg-red-50 rounded"
            aria-label={`Remove ${node.name}`}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
        {(childrenByParent[node.id] || []).map(child => renderNode(child, depth + 1))}
      </div>
    );
  };

  const nodeLevel = Number(nodeForm.hierarchy_level);
  const canSubmitNode =
    nodeForm.name.trim() && nodeLevel && nodeForm.specialization && (nodeLevel >= 17 || nodeForm.parent_id);

  return (
    <div className="space-y-4">
      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="flex-1 text-red-700 text-sm font-medium">{actionError}</p>
          <button onClick={() => setActionError(null)} className="text-red-600 hover:text-red-800"><X className="w-5 h-5" /></button>
        </div>
      )}
      {actionSuccess && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <p className="flex-1 text-green-700 text-sm font-medium">{actionSuccess}</p>
          <button onClick={() => setActionSuccess(null)} className="text-green-600 hover:text-green-800"><X className="w-5 h-5" /></button>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => setShowAddNode(true)}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Org Node
        </button>
        <button
          onClick={() => setShowDepartments(true)}
          className="flex items-center gap-2 px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium"
        >
          Manage Departments
        </button>
      </div>

      {!loading && (
        <div className="rounded-lg border border-gray-200 p-4">
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Departments ({departments.length})</h4>
          {departments.length === 0 ? (
            <p className="text-sm text-gray-500">No departments yet. Use "Manage Departments" to add one to a business unit.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {departments.map(dept => (
                <span key={dept.id} className="px-3 py-1 bg-blue-50 border border-blue-200 text-blue-800 text-xs font-medium rounded-full">
                  {dept.name} · {dept.business_unit_name} · {orgNodes.filter(n => n.department_id === dept.id).length} nodes
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : orgNodes.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>The org chart is empty. Start with the top of the organization (Level 17) - every other seat must report to someone.</p>
        </div>
      ) : (
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-2">
          {childrenByParent.root.map(node => renderNode(node, 0))}
        </div>
      )}

      {showAddNode && (
        <SimpleModal isOpen={true} onClose={closeAddNode} title="Add Organizational Node">
          <form onSubmit={handleAddNode} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                type="text"
                value={nodeForm.name}
                onChange={(e) => setNodeForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g., Jane Smith or Recruitment Lead - East"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Hierarchy Level *</label>
                <select
                  value={nodeForm.hierarchy_level}
                  onChange={(e) => setNodeForm(f => ({ ...f, hierarchy_level: e.target.value, parent_id: "" }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select level</option>
                  {reference.levels.map(l => (
                    <option key={l.level} value={l.level}>L{l.level} · {l.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Specialization *</label>
                <select
                  value={nodeForm.specialization}
                  onChange={(e) => setNodeForm(f => ({ ...f, specialization: e.target.value, parent_id: "" }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select specialization</option>
                  {reference.specializations.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <select
                value={nodeForm.department_id}
                onChange={(e) => setNodeForm(f => ({ ...f, department_id: e.target.value, parent_id: "" }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">No department (not tied to a business unit)</option>
                {departments.map(d => (
                  <option key={d.id} value={d.id}>{d.name} · {d.business_unit_name}</option>
                ))}
              </select>
            </div>
            {nodeLevel > 0 && nodeLevel < 17 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reports To *</label>
                <select
                  value={nodeForm.parent_id}
                  onChange={(e) => setNodeForm(f => ({ ...f, parent_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select supervisor</option>
                  {eligibleParents.map(p => (
                    <option key={p.id} value={p.id}>{p.name} (L{p.hierarchy_level} · {p.specialization})</option>
                  ))}
                </select>
                {nodeForm.specialization && eligibleParents.length === 0 && (
                  <p className="text-xs text-amber-600 mt-1">
                    No eligible supervisor. Level {nodeLevel} must report to Level {nodeLevel + 1}-{Math.min(nodeLevel + 2, 17)}
                    {nodeLevel < 13 ? " in the same specialization (unless the supervisor is Level 13+)" : ""}.
                  </p>
                )}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-4">
              <button type="button" onClick={closeAddNode} className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50">
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={submittingNode || !canSubmitNode}
              >
                {submittingNode ? "Adding..." : "Add Node"}
              </button>
            </div>
          </form>
        </SimpleModal>
      )}

      {showDepartments && (
        <SimpleModal isOpen={true} onClose={() => { setShowDepartments(false); setEditingDept(null); }} title="Manage Departments">
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {departments.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No departments yet</p>
            ) : (
              departments.map(dept => (
                <div key={dept.id} className="flex items-center justify-between bg-gray-50 p-3 rounded border border-gray-200">
                  <div>
                    <span className="text-sm font-medium text-gray-900">{dept.name}</span>
                    <span className="ml-2 text-xs text-gray-500">{dept.business_unit_name}</span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setEditingDept({ id: dept.id, name: dept.name, business_unit_id: String(dept.business_unit_id) })}
                      className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                      aria-label={`Edit ${dept.name}`}
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteDepartment(dept)}
                      className="p-1 text-red-600 hover:bg-red-50 rounded"
                      aria-label={`Delete ${dept.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <form onSubmit={handleSaveDepartment} className="mt-4 space-y-3 bg-blue-50 p-3 rounded border border-blue-200">
            <p className="text-sm font-medium text-gray-800">{editingDept ? "Edit department" : "Add department"}</p>
            <input
              type="text"
              value={(editingDept || deptForm).name}
              onChange={(e) => editingDept
                ? setEditingDept(d => ({ ...d, name: e.target.value }))
                : setDeptForm(d => ({ ...d, name: e.target.value }))}
              placeholder="Department name"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-bx-orange"
            />
            <select
              value={(editingDept || deptForm).business_unit_id}
              onChange={(e) => editingDept
                ? setEditingDept(d => ({ ...d, business_unit_id: e.target.value }))
                : setDeptForm(d => ({ ...d, business_unit_id: e.target.value }))}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:border-bx-orange"
            >
              <option value="">Select business unit</option>
              {businessUnits.map(bu => (
                <option key={bu.id} value={bu.id}>{bu.display_name || bu.name}</option>
              ))}
            </select>
            <div className="flex gap-2 justify-end">
              {editingDept && (
                <button type="button" onClick={() => setEditingDept(null)} className="px-3 py-1 text-xs text-gray-700 border border-gray-300 rounded hover:bg-gray-50">
                  Cancel
                </button>
              )}
              <button
                type="submit"
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-60"
                disabled={!(editingDept || deptForm).name.trim() || !(editingDept || deptForm).business_unit_id}
              >
                {editingDept ? "Save" : "Add Department"}
              </button>
            </div>
          </form>
        </SimpleModal>
      )}
    </div>
  );
}

// LOCATIONS SECTION (DELIVERY CENTERS)

// The delivery-centers CRUD lives in users_access_control.py, which is
// mounted at /api/admin/users-access-control (not the bare /delivery-centers
// this screen used to call) - pass the full path so apiRequest's "starts
// with /api" check uses it as-is instead of prepending /api/v1 again.
const DELIVERY_CENTERS_PATH = '/api/v1/api/admin/users-access-control/delivery-centers';

function LocationsSection() {
  const navigate = useNavigate();
  const [deliveryCenters, setDeliveryCenters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  useEffect(() => {
    loadDeliveryCenters();
  }, []);

  const loadDeliveryCenters = async () => {
    try {
      setLoading(true);
      const res = await apiRequest(DELIVERY_CENTERS_PATH);
      setDeliveryCenters(res.data?.delivery_centers || []);
      setLoadError(null);
    } catch (err) {
      console.error("Failed to load delivery centers:", err);
      setLoadError("Failed to load delivery centers");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (dc) => {
    navigate(`/admin/users-access-control/delivery-centers/${dc.id}/edit`);
  };

  const handleDelete = async (dcId) => {
    if (!window.confirm("Are you sure you want to delete this delivery center?")) return;
    try {
      await apiRequest(`${DELIVERY_CENTERS_PATH}/${dcId}`, { method: "DELETE" });
      setActionSuccess("Delivery Center deleted");
      loadDeliveryCenters();
    } catch (err) {
      console.error("Failed to delete delivery center:", err);
      setLoadError("Failed to delete delivery center");
    }
  };

  return (
    <div className="space-y-4">
      {/* Action Success Banner */}
      {actionSuccess && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
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

      {loadError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-start justify-between">
          <p className="text-rose-700 text-sm font-medium">{loadError}</p>
          <button onClick={() => setLoadError(null)} className="text-rose-600 hover:text-rose-800 flex-shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {hasPermission("delivery-centers", "create") && (
        <button
          onClick={() => navigate('/admin/users-access-control/delivery-centers/create')}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Delivery Center
        </button>
      )}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : deliveryCenters.length === 0 ? (
        <p className="text-sm text-gray-500">No delivery centers yet. Create one to get started.</p>
      ) : (
        <div className="space-y-3">
          {deliveryCenters.map((dc) => (
            <div key={dc.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <h4 className="font-semibold text-gray-900">{dc.name}</h4>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    dc.center_type === "HQ"
                      ? "bg-purple-100 text-purple-800"
                      : "bg-blue-100 text-blue-800"
                  }`}>
                    {dc.center_type}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-2 text-sm text-gray-600">
                  <div><span className="font-medium">Location:</span> {dc.city}, {dc.country}</div>
                  <div><span className="font-medium">Headcount:</span> {dc.headcount}</div>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(dc)}
                  className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDelete(dc.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

  const navItemClasses = "px-4 py-2 font-medium border-b-2 transition whitespace-nowrap flex items-center gap-2 cursor-pointer";
  const activeNavClasses = "border-blue-600 text-blue-600";
  const inactiveNavClasses = "border-transparent text-gray-600 hover:text-gray-900";

  // Navigation items configuration
  const navItems = [
    { id: "users", label: "Users", icon: Users, href: "/admin/users-access-control/users" },
    { id: "business-units", label: "Business Units", icon: Building2, href: "/admin/users-access-control/business-units" },
    { id: "delivery-centers", label: "Delivery Centers", icon: MapPin, href: "/admin/users-access-control/delivery-centers" },
    { id: "organizational-hierarchy", label: "Organizational Hierarchy", icon: Globe, href: "/admin/users-access-control/organizational-hierarchy" },
    { id: "role-templates", label: "Role Templates", icon: null, label2: "📋", href: "/admin/users-access-control/role-templates" }
  ];

  // Check if user has permission to manage role templates (Super User, Admin, CEO)
  const hrmsRole = localStorage.getItem("hrms_role") || "";
  const permissionRole = localStorage.getItem("permission_role") || "";
  const hrmsPermissionsStr = localStorage.getItem("hrms_permissions") || "[]";
  let hrmsPermissions = [];
  try {
    const parsed = JSON.parse(hrmsPermissionsStr);
    hrmsPermissions = Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    // If parsing fails, use empty array
    hrmsPermissions = [];
  }

  const canManageRoleTemplates = hrmsRole.toLowerCase() === "admin" ||
                                 hrmsRole.toLowerCase() === "super user" ||
                                 permissionRole.toLowerCase() === "admin" ||
                                 permissionRole.toLowerCase() === "super user" ||
                                 hrmsPermissions.some(p => p.includes("role") && p.includes("manage")) ||
                                 hrmsPermissions.some(p => p.includes("rbac") && p.includes("manage")) ||
                                 currentUserPermissions?.["role.manage"];

  // Determine the current nav section ID from activeTab
  const currentNavId = Object.keys(sectionMap).find(key => sectionMap[key] === activeTab) || "users";

  return (
    <div className="mx-auto max-w-7xl p-6">
      <Card title="Users & Access Control">
        {/* Navigation Breadcrumbs/Links */}
        <div className="flex gap-2 mb-6 border-b overflow-x-auto">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = currentNavId === item.id;
            return (
              <button
                key={item.id}
                onClick={() => navigate(item.href)}
                className={`${navItemClasses} ${isActive ? activeNavClasses : inactiveNavClasses}`}
              >
                {Icon && <Icon className="h-4 w-4" />}
                {item.label2 && <span>{item.label2}</span>}
                {item.label}
              </button>
            );
          })}
        </div>

        {/* Section Content - Rendered based on URL param */}
        {!activeTab ? (
          // Invalid section - show 404
          <div className="p-6 text-center">
            <h2 className="text-xl font-semibold text-red-600 mb-2">Section Not Found</h2>
            <p className="text-gray-600 mb-4">The requested section does not exist.</p>
            <button
              onClick={() => navigate("/admin/users-access-control/users")}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Go to Users
            </button>
          </div>
        ) : activeTab === "users" ? (
          <UsersSection
            loading={loading}
            error={error}
            users={users}
            roles={roles}
            currentUserPermissions={currentUserPermissions}
          />
        ) : activeTab === "business-units" ? (
          <BusinessUnitsSection />
        ) : activeTab === "locations" ? (
          <LocationsSection />
        ) : activeTab === "hierarchy" ? (
          <OrganizationalHierarchySection />
        ) : activeTab === "templates" ? (
          <RoleTemplatesSection
            loading={loading}
            error={error}
            modules={modules}
            roles={roles}
            setRoles={setRoles}
            users={users}
          />
        ) : null}
      </Card>
    </div>
  );
}
