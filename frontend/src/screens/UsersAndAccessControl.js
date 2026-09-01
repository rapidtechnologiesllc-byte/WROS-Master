// Users & Access Control Management
// Nested route structure: /admin/users-access-control/:section
// Sections: users, business-units, delivery-centers, organizational-hierarchy, role-templates

import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Plus, Edit2, Trash2, Lock, Users, Building2, MapPin, Globe
} from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { toast } from "react-toastify";
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

// ============================================================================
// USERS SECTION
// ============================================================================

function UsersSection({ loading, error, users, roles, currentUserPermissions = {}, employees = [] }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const [businessUnits, setBusinessUnits] = useState([
    { id: 1, name: "North America", bu_name: "North America" },
    { id: 2, name: "Europe", bu_name: "Europe" },
    { id: 3, name: "Asia Pacific", bu_name: "Asia Pacific" }
  ]);

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

    setBusy(true);
    try {
      await deleteHrUser(selectedUserId);
      toast.success("User deleted successfully.");
      setSelectedUserId("");
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to delete user.");
    } finally {
      setBusy(false);
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUserId) return;
    if (!resetForm.new_password.trim()) {
      toast.error("New password is required.");
      return;
    }

    setBusy(true);
    try {
      await apiRequest(`/admin/users/${selectedUserId}/reset-password`, {
        method: "PUT",
        body: JSON.stringify({ new_password: resetForm.new_password })
      });
      toast.success("Password reset successfully.");
      setShowResetModal(false);
      setResetForm({ new_password: "" });
      setSelectedUserId("");
    } catch (err) {
      toast.error(err.message || "Failed to reset password.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading users...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Search users..."
          value={searchTerm}
          onChange={(val) => setSearchTerm(val)}
          className="max-w-xs"
        />
        {hasPermission("user", "create") && (
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


// ============================================================================
// ROLE TEMPLATES SECTION (showing all templates with their permissions)
// ============================================================================

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

      toast.success(`Permission ${newState ? 'enabled' : 'disabled'} for ${resourceName} - ${verb}`);
    } catch (err) {
      toast.error(err.message || `Failed to update permission for ${resourceName}`);
    } finally {
      setToggling({ ...toggling, [key]: false });
    }
  };

  const handleToggleModule = async (moduleName, displayResources, shouldEnable) => {
    if (!editingTemplateId) return;

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

      toast.success(`Module ${moduleName} ${shouldEnable ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      toast.error(err.message || `Failed to toggle module ${moduleName}`);
    } finally {
      setToggling({ ...toggling, [moduleName]: false });
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading templates...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  const handleCreateRole = async () => {
    if (!createRoleForm.name.trim()) {
      toast.error("Role name is required.");
      return;
    }

    if (!canCreateTemplate()) {
      toast.error("Please enable at least one module and select permissions.");
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
      toast.success("Role created successfully.");
      setShowCreateModal(false);
      setCreateRoleForm({ name: "", description: "" });
      setCreateTemplatePermissions({});
      setCreateTemplateModuleStates({});
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to create role.");
    } finally {
      setCreatingTemplate(false);
    }
  };

  const handleToggleTemplateStatus = async (templateId, currentStatus) => {
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

      toast.success(`Template ${!currentStatus ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      console.error("Failed to toggle template status:", err);
      toast.error(err.message || "Failed to toggle template status");
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
                  <span className="text-xs text-gray-500">{userCount} user{userCount !== 1 ? 's' : ''}</span>
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
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

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

  const canManageRoles = hasPermission("user_roles", "edit");

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
      } catch (rolesErr) {
        console.warn("Failed to load role templates (may require permission):", rolesErr);
        setRoles([]);
      }

      // Load modules/resources (optional - may fail due to permissions)
      let modulesRes = null;
      try {
        const modsRes = await listModulesAndResources();
        modulesRes = { modules: modsRes };
        setModules(modulesRes?.modules || []);
      } catch (modulesErr) {
        console.warn("Failed to load modules and verbs (may require rbac.view permission):", modulesErr);
        setModules([]);
      }

      // Fetch current user permissions
      try {
        const meData = await getHrMe();
        if (meData?.permissions) {
          setCurrentUserPermissions(meData.permissions);
        }
      } catch (permErr) {
        console.warn("Failed to load user permissions:", permErr);
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
      toast.error("Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

// ============================================================================
// BUSINESS UNITS SECTION (from AdminSettings)
// ============================================================================

function BusinessUnitsSection() {
  const navigate = useNavigate();
  const [businessUnits, setBusinessUnits] = useState([]);

  useEffect(() => {
    loadBusinessUnits();
  }, []);

  const loadBusinessUnits = async () => {
    try {
      const response = await apiRequest("/admin/certifications/business-units", {
        method: "GET"
      });
      const busData = Array.isArray(response) ? response : response?.data || [];
      setBusinessUnits(busData);
    } catch (err) {
      console.error("Failed to load business units:", err);
      setBusinessUnits([]);
    }
  };


  const handleDeleteBusinessUnit = async (buId) => {
    if (!window.confirm("Are you sure you want to delete this business unit?")) return;
    try {
      await apiRequest(`/rbac/business-units/${buId}`, { method: "DELETE" });
      loadBusinessUnits();
      toast.success("Business Unit deleted successfully");
    } catch (err) {
      toast.error("Failed to delete business unit");
    }
  };

  return (
    <div className="space-y-4">
      {hasPermission("business_unit", "create") && (
        <button
          onClick={() => navigate('/admin/users-access-control/business-units/create')}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Business Unit
        </button>
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

// ============================================================================
// ORGANIZATIONAL HIERARCHY SECTION
// ============================================================================

function OrganizationalHierarchySection() {
  const POSITIONS = [
    { id: 1, name: "CEO" },
    { id: 2, name: "Partner" },
    { id: 3, name: "BU Head" },
    { id: 4, name: "Senior Director" },
    { id: 5, name: "Director" },
    { id: 6, name: "Technical Manager" },
    { id: 7, name: "Senior Manager" },
    { id: 8, name: "Manager" },
    { id: 9, name: "Team Lead" },
    { id: 10, name: "Senior Consultant" }
  ];

  const [orgNodes, setOrgNodes] = useState([]);
  const [positions, setPositions] = useState(POSITIONS);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [showAddOrgNodeModal, setShowAddOrgNodeModal] = useState(false);
  const [showPositionsManager, setShowPositionsManager] = useState(false);
  const [showAddPositionModal, setShowAddPositionModal] = useState(false);
  const [editingOrgNodeId, setEditingOrgNodeId] = useState(null);
  const [newOrgNodeEmployeeName, setNewOrgNodeEmployeeName] = useState("");
  const [newOrgNodePosition, setNewOrgNodePosition] = useState("");
  const [newOrgNodeReportsTo, setNewOrgNodeReportsTo] = useState("");
  const [newOrgNodeBusinessUnit, setNewOrgNodeBusinessUnit] = useState("");
  const [newOrgNodeLocation, setNewOrgNodeLocation] = useState("");
  const [editOrgNodeEmployeeName, setEditOrgNodeEmployeeName] = useState("");
  const [editOrgNodePosition, setEditOrgNodePosition] = useState("");
  const [editOrgNodeReportsTo, setEditOrgNodeReportsTo] = useState("");
  const [editOrgNodeBusinessUnit, setEditOrgNodeBusinessUnit] = useState("");
  const [editOrgNodeLocation, setEditOrgNodeLocation] = useState("");
  const [newPositionName, setNewPositionName] = useState("");
  const [newPositionRoleTemplate, setNewPositionRoleTemplate] = useState("");
  const [isSubmittingOrgNode, setIsSubmittingOrgNode] = useState(false);

  useEffect(() => {
    loadOrgNodes();
    loadBusinessUnits();
  }, []);

  const loadOrgNodes = async () => {
    try {
      // Fetch users instead of org nodes (org nodes endpoint doesn't exist yet)
      const { data } = await apiRequest("/hr/users/all");
      const usersList = data?.users || [];
      // Convert users to org nodes format
      const nodes = usersList.map(u => ({
        id: u.user_id,
        employee_name: u.user_name,
        position: u.permission_role || u.user_role,
        business_unit: u.business_unit_name,
        reports_to: null,
        location: null
      }));
      setOrgNodes(Array.isArray(nodes) ? nodes : []);
    } catch (err) {
      console.error("Failed to load org nodes:", err);
    }
  };

  const loadBusinessUnits = async () => {
    try {
      const response = await apiRequest("/admin/certifications/business-units");
      const busData = Array.isArray(response) ? response : response?.data || [];
      setBusinessUnits(busData);
    } catch (err) {
      console.error("Failed to load business units:", err);
    }
  };

  const handleAddOrgNode = async (e) => {
    e.preventDefault();
    if (!newOrgNodeEmployeeName.trim() || !newOrgNodePosition.trim()) {
      toast.error("Employee name and position are required");
      return;
    }
    setIsSubmittingOrgNode(true);
    try {
      const payload = {
        employee_name: newOrgNodeEmployeeName,
        position_id: parseInt(newOrgNodePosition),
        reports_to: newOrgNodeReportsTo || null,
        business_unit: newOrgNodeBusinessUnit || null,
        location: newOrgNodeLocation || null
      };

      await apiRequest("/org/nodes", { method: "POST", body: JSON.stringify(payload) });
      toast.success("Org node created successfully");
      loadOrgNodes();
      setShowAddOrgNodeModal(false);
      setNewOrgNodeEmployeeName("");
      setNewOrgNodePosition("");
      setNewOrgNodeReportsTo("");
      setNewOrgNodeBusinessUnit("");
      setNewOrgNodeLocation("");
    } catch (err) {
      toast.error(err?.message || "Failed to create org node");
    } finally {
      setIsSubmittingOrgNode(false);
    }
  };

  const handleAddPosition = (e) => {
    e.preventDefault();
    if (newPositionName.trim()) {
      setPositions([...positions, {
        id: Math.max(...positions.map(p => p.id), 0) + 1,
        name: newPositionName,
        role_template_id: newPositionRoleTemplate ? parseInt(newPositionRoleTemplate) : null
      }]);
      setNewPositionName("");
      setNewPositionRoleTemplate("");
      setShowAddPositionModal(false);
      toast.success("Position added");
    }
  };

  const handleDeletePosition = (posId) => {
    if (positions.length <= 1) {
      toast.error("You must have at least one position");
      return;
    }
    setPositions(positions.filter(p => p.id !== posId));
  };

  const handleEditOrgNode = (node) => {
    setEditingOrgNodeId(node.id);
    setEditOrgNodeEmployeeName(node.employee_name);
    setEditOrgNodePosition(node.position_id ? node.position_id.toString() : "");
    setEditOrgNodeReportsTo(node.reports_to ? node.reports_to.toString() : "");
    setEditOrgNodeBusinessUnit(node.business_unit || "");
    setEditOrgNodeLocation(node.location || "");
  };

  const handleSaveEditedOrgNode = () => {
    if (!editOrgNodeEmployeeName.trim() || !editOrgNodePosition.trim()) {
      toast.error("Employee name and position are required");
      return;
    }
    setOrgNodes(orgNodes.map(node =>
      node.id === editingOrgNodeId
        ? {
            ...node,
            employee_name: editOrgNodeEmployeeName,
            position_id: parseInt(editOrgNodePosition),
            reports_to: editOrgNodeReportsTo ? parseInt(editOrgNodeReportsTo) : null,
            business_unit: editOrgNodeBusinessUnit,
            location: editOrgNodeLocation
          }
        : node
    ));
    setEditingOrgNodeId(null);
    setEditOrgNodeEmployeeName("");
    setEditOrgNodePosition("");
    setEditOrgNodeReportsTo("");
    setEditOrgNodeBusinessUnit("");
    setEditOrgNodeLocation("");
    toast.success("Org node updated successfully");
  };

  const handleDeleteOrgNode = (nodeId) => {
    if (window.confirm("Are you sure you want to remove this person from the organizational hierarchy?")) {
      setOrgNodes(orgNodes.filter(n => n.id !== nodeId));
      toast.success("Node removed");
    }
  };

  const getPositionName = (positionId) => positions.find(p => p.id === positionId)?.name || "Unknown";
  const getBusinessUnitName = (buId) => businessUnits.find(bu => bu.id === buId)?.name || "-";

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          onClick={() => setShowAddOrgNodeModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Org Node
        </button>
        <button
          onClick={() => setShowPositionsManager(!showPositionsManager)}
          className="flex items-center gap-2 px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium"
        >
          Manage Positions
        </button>
      </div>

      {showPositionsManager && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
          <div className="flex justify-between items-center">
            <h4 className="font-semibold text-gray-900">Position Reference List</h4>
            <button
              onClick={() => setShowAddPositionModal(!showAddPositionModal)}
              className="flex items-center gap-1 px-3 py-1 text-sm text-blue-600 hover:bg-blue-100 rounded"
            >
              <Plus className="h-4 w-4" /> Add Position
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {positions.map((pos) => (
              <div key={pos.id} className="flex items-center justify-between bg-white p-2 rounded border border-gray-200">
                <span className="text-sm text-gray-700">{pos.name}</span>
                <button
                  onClick={() => handleDeletePosition(pos.id)}
                  className="text-red-600 hover:text-red-700 p-1"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
          {showAddPositionModal && (
            <div className="bg-white p-3 rounded border border-blue-300 space-y-2">
              <input
                type="text"
                value={newPositionName}
                onChange={(e) => setNewPositionName(e.target.value)}
                placeholder="Enter new position name"
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:border-bx-orange"
              />
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Role Template (Optional)</label>
                <select
                  value={newPositionRoleTemplate}
                  onChange={(e) => setNewPositionRoleTemplate(e.target.value)}
                  className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:border-bx-orange"
                >
                  <option value="">No role template</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">Optionally assign a role template to this position</p>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowAddPositionModal(false); setNewPositionRoleTemplate(""); }}
                  className="px-3 py-1 text-xs text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddPosition}
                  className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                  disabled={!newPositionName.trim()}
                >
                  Add
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {orgNodes.length > 0 ? (
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 space-y-2">
          <div className="text-sm text-gray-600 mb-4">Organizational Structure</div>
          {orgNodes
            .filter(node => !node.reports_to)
            .map((node) => (
              <div key={node.id} className="border-l-4 border-bx-orange pl-4 py-2">
                <div className="flex items-center justify-between bg-white p-3 rounded border border-gray-200 hover:bg-gray-50">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-gray-900">{node.employee_name}</h4>
                      <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">
                        {getPositionName(node.position_id)}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEditOrgNode(node)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteOrgNode(node.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <p>No organizational nodes created yet. Click "Add Org Node" to add people to the organizational hierarchy.</p>
        </div>
      )}

      {showAddOrgNodeModal && (
        <SimpleModal isOpen={true} onClose={() => { setShowAddOrgNodeModal(false); setNewOrgNodeEmployeeName(""); setNewOrgNodePosition(""); setNewOrgNodeReportsTo(""); setNewOrgNodeBusinessUnit(""); setNewOrgNodeLocation(""); }} title="Add Organizational Node">
          <form onSubmit={handleAddOrgNode} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Employee Name *</label>
              <input
                type="text"
                value={newOrgNodeEmployeeName}
                onChange={(e) => setNewOrgNodeEmployeeName(e.target.value)}
                placeholder="e.g., John Smith"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Position *</label>
              <select
                value={newOrgNodePosition}
                onChange={(e) => setNewOrgNodePosition(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">Select a position</option>
                {positions.map((pos) => (
                  <option key={pos.id} value={pos.id}>{pos.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Reports To</label>
              <select
                value={newOrgNodeReportsTo}
                onChange={(e) => setNewOrgNodeReportsTo(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">CEO / Top Level</option>
                {orgNodes.map((node) => (
                  <option key={node.id} value={node.id}>{node.employee_name} ({getPositionName(node.position_id)})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit</label>
              <select
                value={newOrgNodeBusinessUnit}
                onChange={(e) => setNewOrgNodeBusinessUnit(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">Select Business Unit</option>
                {businessUnits.map((bu) => (
                  <option key={bu.id} value={bu.id}>{bu.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={newOrgNodeLocation}
                onChange={(e) => setNewOrgNodeLocation(e.target.value)}
                placeholder="e.g., Austin, TX"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => { setShowAddOrgNodeModal(false); setNewOrgNodeEmployeeName(""); setNewOrgNodePosition(""); setNewOrgNodeReportsTo(""); setNewOrgNodeBusinessUnit(""); setNewOrgNodeLocation(""); }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={isSubmittingOrgNode || !newOrgNodeEmployeeName.trim() || !newOrgNodePosition.trim()}
              >
                {isSubmittingOrgNode ? "Adding..." : "Add Node"}
              </button>
            </div>
          </form>
        </SimpleModal>
      )}

      {editingOrgNodeId && (
        <SimpleModal isOpen={true} onClose={() => { setEditingOrgNodeId(null); setEditOrgNodeEmployeeName(""); setEditOrgNodePosition(""); setEditOrgNodeReportsTo(""); setEditOrgNodeBusinessUnit(""); setEditOrgNodeLocation(""); }} title="Edit Organizational Node">
          <form onSubmit={(e) => { e.preventDefault(); handleSaveEditedOrgNode(); }} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Employee Name *</label>
              <input
                type="text"
                value={editOrgNodeEmployeeName}
                onChange={(e) => setEditOrgNodeEmployeeName(e.target.value)}
                placeholder="e.g., John Smith"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Position *</label>
              <select
                value={editOrgNodePosition}
                onChange={(e) => setEditOrgNodePosition(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">Select a position</option>
                {positions.map((pos) => (
                  <option key={pos.id} value={pos.id}>{pos.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Reports To</label>
              <select
                value={editOrgNodeReportsTo}
                onChange={(e) => setEditOrgNodeReportsTo(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">CEO / Top Level</option>
                {orgNodes.filter(n => n.id !== editingOrgNodeId).map((node) => (
                  <option key={node.id} value={node.id}>{node.employee_name} ({getPositionName(node.position_id)})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit</label>
              <select
                value={editOrgNodeBusinessUnit}
                onChange={(e) => setEditOrgNodeBusinessUnit(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="">Select Business Unit</option>
                {businessUnits.map((bu) => (
                  <option key={bu.id} value={bu.id}>{bu.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={editOrgNodeLocation}
                onChange={(e) => setEditOrgNodeLocation(e.target.value)}
                placeholder="e.g., Austin, TX"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => { setEditingOrgNodeId(null); setEditOrgNodeEmployeeName(""); setEditOrgNodePosition(""); setEditOrgNodeReportsTo(""); setEditOrgNodeBusinessUnit(""); setEditOrgNodeLocation(""); }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={!editOrgNodeEmployeeName.trim() || !editOrgNodePosition.trim()}
              >
                Save Changes
              </button>
            </div>
          </form>
        </SimpleModal>
      )}
    </div>
  );
}

// ============================================================================
// LOCATIONS SECTION (DELIVERY CENTERS)
// ============================================================================

function LocationsSection() {
  const navigate = useNavigate();
  const [deliveryCenters, setDeliveryCenters] = useState([
    { id: 1, name: "Austin, TX", type: "HQ", buServed: ["North America"], headcount: 150, city: "Austin", country: "USA" },
    { id: 2, name: "Youngstown, OH", type: "Delivery", buServed: ["North America"], headcount: 300, city: "Youngstown", country: "USA" },
  ]);

  const handleDelete = (dcId) => {
    if (window.confirm("Are you sure you want to delete this delivery center?")) {
      setDeliveryCenters(deliveryCenters.filter(dc => dc.id !== dcId));
      toast.success("Delivery Center deleted");
    }
  };

  return (
    <div className="space-y-4">
      {hasPermission("delivery_center", "create") && (
        <button
          onClick={() => navigate('/admin/users-access-control/delivery-centers/create')}
          className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
        >
          <Plus className="h-4 w-4" /> Add Delivery Center
        </button>
      )}
      <div className="space-y-3">
        {deliveryCenters.map((dc) => (
          <div key={dc.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h4 className="font-semibold text-gray-900">{dc.name}</h4>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  dc.type === "HQ"
                    ? "bg-purple-100 text-purple-800"
                    : "bg-blue-100 text-blue-800"
                }`}>
                  {dc.type}
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
  const hrmsPermissions = JSON.parse(hrmsPermissionsStr) || [];

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
