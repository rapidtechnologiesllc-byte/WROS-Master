// Users & Access Control Management
// Simplified to show users with integrated role assignment

import React, { useEffect, useMemo, useState } from "react";
import {
  Plus, Edit2, Trash2, Lock
} from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { toast } from "react-toastify";
import { canEdit, canDelete } from "../services/permissions";
import {
  getAllUsers,
  createHrUser,
  updateHrUser,
  deleteHrUser,
  updateUserPermissions,
  getUserPermissions
} from "../services/api/users";
import {
  listRoles,
  getModulesAndVerbs,
  grantPermission,
  revokePermission
} from "../services/api/rbac";
import { apiRequest } from "../services/api/client";
import { getHrMe } from "../services/api/users";

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
    "Admin": ["rbac", "users", "tenant_config", "locale", "ai_config"]
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

function UsersSection({ loading, error, users, roles, currentUserPermissions = {} }) {
  const [busy, setBusy] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const [businessUnits, setBusinessUnits] = useState([]);

  const [createForm, setCreateForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    user_role: roles[0]?.name || "",
    business_unit_id: "",
    role_ids: [] // Multi-role support
  });

  const [editForm, setEditForm] = useState({
    user_name: "",
    user_role: "",
    expandAllPermissions: false,
    expanded_candidates: false,
    expanded_jobs: false,
    expanded_interviews: false,
    expanded_admin: false,
    perm_candidates_view: true,
    perm_candidates_create: true,
    perm_candidates_edit: true,
    perm_candidates_delete: true,
    perm_jobs_view: true,
    perm_jobs_create: true,
    perm_jobs_edit: true,
    perm_jobs_delete: true,
    perm_interviews_view: true,
    perm_interviews_create: true,
    perm_interviews_edit: true,
    perm_interviews_delete: true,
    perm_admin_view: true,
    perm_admin_create: true,
    perm_admin_edit: true,
    perm_admin_delete: true
  });

  const [resetForm, setResetForm] = useState({
    new_password: ""
  });

  // Load business units on mount
  useEffect(() => {
    const loadBusinessUnits = async () => {
      try {
        const response = await apiRequest("/bu-context/available-buses");
        const busData = response?.business_units || response?.data || response || [];
        setBusinessUnits(Array.isArray(busData) ? busData : []);
      } catch (err) {
        console.error("Failed to load business units:", err);
        setBusinessUnits([]);
      }
    };
    loadBusinessUnits();
  }, []);

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

  const handleCreate = async () => {
    if (!createForm.user_name.trim()) {
      toast.error("User name is required.");
      return;
    }
    if (!createForm.user_email.trim()) {
      toast.error("User email is required.");
      return;
    }
    if (!createForm.user_password.trim()) {
      toast.error("Password is required.");
      return;
    }

    // Support both multi-role (new) and single role (legacy) modes
    const roleIds = createForm.role_ids?.length > 0 ? createForm.role_ids :
                    (createForm.user_role ? [roles.find(r => r.name === createForm.user_role)?.id].filter(Boolean) : []);

    if (roleIds.length === 0) {
      toast.error("At least one role is required.");
      return;
    }

    setBusy(true);
    try {
      // If BU is selected, use new multi-role endpoint
      if (createForm.business_unit_id) {
        await apiRequest("/users/create-with-roles", "POST", {
          user_name: createForm.user_name,
          user_email: createForm.user_email,
          user_password: createForm.user_password,
          business_unit_id: parseInt(createForm.business_unit_id, 10),
          role_ids: roleIds.map(id => parseInt(id, 10))
        });
      } else {
        // Legacy single-role endpoint
        await createHrUser({
          user_name: createForm.user_name,
          user_email: createForm.user_email,
          user_password: createForm.user_password,
          user_role: createForm.user_role
        });
      }
      toast.success("User created successfully.");
      setShowCreateModal(false);
      setCreateForm({ user_name: "", user_email: "", user_password: "", user_role: roles[0]?.name || "", business_unit_id: "", role_ids: [] });
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to create user.");
    } finally {
      setBusy(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!selectedUserId) return;
    if (!editForm.user_name.trim()) {
      toast.error("User name is required.");
      return;
    }

    setBusy(true);
    try {
      // Update user name and role
      await updateHrUser(selectedUserId, {
        user_name: editForm.user_name,
        user_role: editForm.user_role
      });

      // Extract permission overrides from editForm
      const permissionOverrides = {};
      for (const key of Object.keys(editForm)) {
        if (key.startsWith("perm_") || key.startsWith("expanded_")) {
          if (key.startsWith("perm_")) {
            permissionOverrides[key] = editForm[key];
          }
        }
      }

      // Save permission overrides if any exist
      if (Object.keys(permissionOverrides).length > 0) {
        await updateUserPermissions(selectedUserId, permissionOverrides);
      }

      toast.success("User updated successfully.");
      setShowEditModal(false);
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to update user.");
    } finally {
      setBusy(false);
    }
  };

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
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-xs"
        />
        <Button
          onClick={() => setShowCreateModal(true)}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          Add User
        </Button>
      </div>

      <Table
        columns={[
          { header: "Name", accessor: "user_name", key: "name" },
          { header: "Email", accessor: "user_email", key: "email" },
          { header: "Role", accessor: "user_role", key: "role" },
          {
            header: "Actions",
            key: "actions",
            cell: (row) => (
              <div className="flex items-center gap-2">
                {canEdit(currentUserPermissions, "user") && (
                  <button
                    onClick={async () => {
                      setSelectedUserId(row.user_id);
                      try {
                        // Fetch saved permissions for this user
                        const savedPermissions = await getUserPermissions(row.user_id);

                        // Merge saved permissions with defaults
                        const defaultPermissions = {
                          expandAllPermissions: false,
                          expanded_candidates: false,
                          expanded_jobs: false,
                          expanded_interviews: false,
                          expanded_admin: false,
                          perm_candidates_view: true,
                          perm_candidates_create: true,
                          perm_candidates_edit: true,
                          perm_candidates_delete: true,
                          perm_jobs_view: true,
                          perm_jobs_create: true,
                          perm_jobs_edit: true,
                          perm_jobs_delete: true,
                          perm_interviews_view: true,
                          perm_interviews_create: true,
                          perm_interviews_edit: true,
                          perm_interviews_delete: true,
                          perm_admin_view: true,
                          perm_admin_create: true,
                          perm_admin_edit: true,
                          perm_admin_delete: true
                        };

                        setEditForm({
                          user_name: safeText(row.user_name),
                          user_role: safeText(row.user_role),
                          ...defaultPermissions,
                          ...savedPermissions
                        });
                      } catch (err) {
                        console.error("Failed to fetch permissions:", err);
                        setEditForm({
                          user_name: safeText(row.user_name),
                          user_role: safeText(row.user_role),
                          expandAllPermissions: false,
                          expanded_candidates: false,
                          expanded_jobs: false,
                          expanded_interviews: false,
                          expanded_admin: false,
                          perm_candidates_view: true,
                          perm_candidates_create: true,
                          perm_candidates_edit: true,
                          perm_candidates_delete: true,
                          perm_jobs_view: true,
                          perm_jobs_create: true,
                          perm_jobs_edit: true,
                          perm_jobs_delete: true,
                          perm_interviews_view: true,
                          perm_interviews_create: true,
                          perm_interviews_edit: true,
                          perm_interviews_delete: true,
                          perm_admin_view: true,
                          perm_admin_create: true,
                          perm_admin_edit: true,
                          perm_admin_delete: true
                        });
                      }
                      setShowEditModal(true);
                    }}
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

      {/* Create User Modal */}
      <SimpleModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create User"
      >
        <div className="space-y-4">
          <Input
            label="Name"
            placeholder="John Doe"
            value={createForm.user_name}
            onChange={(e) => setCreateForm({ ...createForm, user_name: e.target.value })}
          />
          <Input
            label="Email"
            type="email"
            placeholder="john@example.com"
            value={createForm.user_email}
            onChange={(e) => setCreateForm({ ...createForm, user_email: e.target.value })}
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={createForm.user_password}
            onChange={(e) => setCreateForm({ ...createForm, user_password: e.target.value })}
          />

          {/* Business Unit Selection (New RBAC) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Business Unit (Optional)</label>
            <select
              value={createForm.business_unit_id}
              onChange={(e) => setCreateForm({ ...createForm, business_unit_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a business unit...</option>
              {businessUnits.map(bu => (
                <option key={bu.id} value={bu.id}>
                  {bu.bu_name || bu.name || `BU ${bu.id}`}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">For multi-role assignment with BU scoping</p>
          </div>

          {/* Multi-Role Selection (New RBAC) */}
          {createForm.business_unit_id && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Roles (Select one or more)</label>
              <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-300 rounded-md p-3 bg-gray-50">
                {roles.map(role => (
                  <label key={role.id} className="flex items-center gap-2 cursor-pointer hover:bg-white p-2 rounded">
                    <input
                      type="checkbox"
                      checked={createForm.role_ids?.includes(role.id) || false}
                      onChange={(e) => {
                        const newRoleIds = e.target.checked
                          ? [...(createForm.role_ids || []), role.id]
                          : (createForm.role_ids || []).filter(id => id !== role.id);
                        setCreateForm({ ...createForm, role_ids: newRoleIds });
                      }}
                      className="w-4 h-4"
                    />
                    <span className="text-sm text-gray-900">{role.name}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1">User will have combined permissions from all selected roles</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Permission Template</label>
            <select
              value={createForm.user_role}
              onChange={(e) => setCreateForm({ ...createForm, user_role: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a template...</option>
              {roles.map(r => {
                const userCount = users.filter(u => u.user_role === r.name).length;
                return (
                  <option key={r.id} value={r.name}>
                    {r.name} ({userCount} user{userCount !== 1 ? 's' : ''})
                  </option>
                );
              })}
            </select>
          </div>
          <div className="flex gap-3 justify-end pt-4">
            <Button
              variant="outline"
              onClick={() => setShowCreateModal(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={busy}
            >
              {busy ? "Creating..." : "Create User"}
            </Button>
          </div>
        </div>
      </SimpleModal>

      {/* Edit User Modal - WITH PERMISSIONS */}
      <SimpleModal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="Edit User"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <Input
            label="Name"
            value={editForm.user_name}
            onChange={(e) => setEditForm({ ...editForm, user_name: e.target.value })}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Permission Template</label>
            <select
              value={editForm.user_role}
              onChange={(e) => setEditForm({ ...editForm, user_role: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a template...</option>
              {roles.map(r => {
                const userCount = users.filter(u => u.user_role === r.name).length;
                return (
                  <option key={r.id} value={r.name}>
                    {r.name} ({userCount} user{userCount !== 1 ? 's' : ''})
                  </option>
                );
              })}
            </select>
          </div>

          {/* Permissions Section */}
          <div className="border-t pt-4 mt-4">
            <div className="mb-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-1">Permissions</h3>
                  <p className="text-xs text-gray-600">Override or customize permissions for this user</p>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded"
                    checked={editForm.expandAllPermissions}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setEditForm({
                        ...editForm,
                        expandAllPermissions: checked,
                        expanded_candidates: checked,
                        expanded_jobs: checked,
                        expanded_interviews: checked,
                        expanded_admin: checked
                      });
                    }}
                  />
                  <span className="text-xs text-gray-700 font-medium">Expand all</span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              {["Candidates", "Jobs", "Interviews", "Admin"].map(category => {
                const expandedKey = `expanded_${category.toLowerCase()}`;
                const isExpanded = editForm.expandAllPermissions || editForm[expandedKey];

                return (
                  <div key={category} className="border rounded-lg">
                    <button
                      type="button"
                      onClick={() => {
                        setEditForm({
                          ...editForm,
                          [expandedKey]: !editForm[expandedKey]
                        });
                      }}
                      className="w-full flex items-center justify-between px-3 py-3 hover:bg-gray-50"
                    >
                      <div className="text-sm font-medium text-gray-900">{category}</div>
                      <div className="text-gray-500 text-lg">
                        {isExpanded ? '▼' : '▶'}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="flex flex-wrap gap-3 px-3 py-3 bg-gray-50 border-t">
                        {["view", "create", "edit", "delete"].map(verb => {
                          const permKey = `perm_${category.toLowerCase()}_${verb}`;
                          return (
                            <label key={verb} className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                className="w-4 h-4 rounded"
                                checked={editForm[permKey] ?? true}
                                onChange={(e) => setEditForm({ ...editForm, [permKey]: e.target.checked })}
                              />
                              <span className="text-sm text-gray-700 capitalize">{verb}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => setShowEditModal(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateUser}
              disabled={busy}
            >
              {busy ? "Updating..." : "Update User"}
            </Button>
          </div>
        </div>
      </SimpleModal>

      {/* Reset Password Modal */}
      <SimpleModal
        isOpen={showResetModal}
        onClose={() => setShowResetModal(false)}
        title="Reset Password"
      >
        <div className="space-y-4">
          <Input
            label="New Password"
            type="password"
            placeholder="••••••••"
            value={resetForm.new_password}
            onChange={(e) => setResetForm({ new_password: e.target.value })}
          />
          <div className="flex gap-3 justify-end pt-4">
            <Button
              variant="outline"
              onClick={() => setShowResetModal(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              onClick={handleResetPassword}
              disabled={busy}
            >
              {busy ? "Resetting..." : "Reset Password"}
            </Button>
          </div>
        </div>
      </SimpleModal>

      {/* User Permissions Modal */}
      <UserPermissionsModal
        isOpen={showPermissionsModal}
        onClose={() => setShowPermissionsModal(false)}
        user={selectedUser}
        roles={roles}
      />
    </div>
  );
}

// ============================================================================
// ROLE TEMPLATES SECTION (showing all templates with their permissions)
// ============================================================================

function RoleTemplatesSection({ loading, error, modules, roles, users }) {
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [toggling, setToggling] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createRoleForm, setCreateRoleForm] = useState({ name: "", description: "" });
  const [creatingTemplate, setCreatingTemplate] = useState(false);

  const filteredRoles = useMemo(() => {
    if (!searchTerm) return roles;
    const term = searchTerm.toLowerCase();
    return roles.filter(r =>
      (r.name || "").toLowerCase().includes(term) ||
      (r.description || "").toLowerCase().includes(term)
    );
  }, [roles, searchTerm]);

  // Count users per template
  const getUserCount = (roleId) => {
    return users.filter(u => u.role_id === roleId).length;
  };

  const editingTemplate = roles.find(r => r.id === editingTemplateId);

  // Convert flat permission list to hierarchical structure { module: { verb: true } }
  const convertPermissionsToHierarchy = (perms) => {
    if (!Array.isArray(perms)) return {};

    const hierarchy = {};
    perms.forEach(perm => {
      // Parse permission name like "candidates_view" -> module="candidates", verb="view"
      const parts = perm.name.split('_');
      if (parts.length >= 2) {
        const verb = parts[parts.length - 1]; // Last part is the verb
        const module = parts.slice(0, -1).join('_'); // Everything else is the module

        if (!hierarchy[module]) {
          hierarchy[module] = {};
        }
        hierarchy[module][verb] = true;
      }
    });
    return hierarchy;
  };

  const editingPermissions = convertPermissionsToHierarchy(editingTemplate?.permissions || []);

  const handleTogglePermission = async (module, verb, currentState) => {
    const key = `${editingTemplateId}_${module}_${verb}`;
    setToggling({ ...toggling, [key]: true });

    try {
      const permissionName = `${module}.${verb}`;
      if (currentState) {
        await revokePermission(editingTemplateId, permissionName);
      } else {
        await grantPermission(editingTemplateId, permissionName);
      }
      toast.success("Permission updated.");
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to update permission.");
    } finally {
      setToggling({ ...toggling, [key]: false });
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading templates...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  const handleCreateRole = async () => {
    if (!createRoleForm.name.trim()) {
      toast.error("Role name is required.");
      return;
    }

    setCreatingTemplate(true);
    try {
      await apiRequest("/rbac/roles", {
        method: "POST",
        body: JSON.stringify({
          name: createRoleForm.name,
          description: createRoleForm.description
        })
      });
      toast.success("Role created successfully.");
      setShowCreateModal(false);
      setCreateRoleForm({ name: "", description: "" });
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to create role.");
    } finally {
      setCreatingTemplate(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Search templates..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-xs"
        />
        <Button
          onClick={() => setShowCreateModal(true)}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          Add New Role
        </Button>
      </div>

      {editingTemplateId ? (
        <div className="border rounded-lg p-6 bg-white">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{editingTemplate?.name}</h3>
              <p className="text-sm text-gray-600">{editingTemplate?.description}</p>
              <p className="text-xs text-gray-500 mt-1">{getUserCount(editingTemplateId)} users using this template</p>
            </div>
            <button
              onClick={() => setEditingTemplateId(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="overflow-x-auto border rounded-lg">
            {(() => {
              const standardVerbs = ["view", "create", "edit", "delete"];
              const modulesAsObjects = Array.isArray(modules)
                ? modules.map((m, i) => ({
                    id: i,
                    name: typeof m === 'string' ? m : m.name
                  }))
                : [];

              return (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="px-4 py-3 text-left font-semibold text-gray-700 min-w-max">Module</th>
                      {standardVerbs.map(verb => (
                        <th key={verb} className="px-4 py-3 text-center font-semibold text-gray-700 text-xs whitespace-nowrap">
                          {verb.charAt(0).toUpperCase() + verb.slice(1)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {modulesAsObjects.map(module => (
                      <tr key={`module_${module.id}_${module.name}`} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap capitalize">{module.name.replace(/_/g, ' ')}</td>
                        {standardVerbs.map(verb => {
                          const key = `${editingTemplateId}_${module.name}_${verb}`;
                          const hasPermission = editingPermissions[module.name]?.[verb] || false;
                          const isToggling = toggling[key];
                          return (
                            <td key={`cell_${module.name}_${verb}`} className="px-4 py-3 text-center">
                              <button
                                onClick={() => handleTogglePermission(module.name, verb, hasPermission)}
                                disabled={isToggling}
                                className={`inline-flex items-center justify-center h-8 px-3 rounded text-sm font-medium transition ${
                                  hasPermission
                                    ? "bg-green-100 text-green-700 hover:bg-green-200"
                                    : "bg-gray-100 text-gray-400 hover:bg-gray-200"
                                }`}
                              >
                                {hasPermission ? "✓" : "○"}
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </div>
        </div>
      ) : (
        <>
          {/* Create Role Modal */}
          <SimpleModal
            isOpen={showCreateModal}
            onClose={() => setShowCreateModal(false)}
            title="Add New Role"
          >
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Role Name</label>
                <input
                  type="text"
                  placeholder="e.g., Senior Recruiter"
                  value={createRoleForm.name}
                  onChange={(e) => setCreateRoleForm({ ...createRoleForm, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
                <textarea
                  placeholder="What permissions does this role have?"
                  value={createRoleForm.description}
                  onChange={(e) => setCreateRoleForm({ ...createRoleForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  rows="3"
                />
              </div>
              <div className="flex gap-3 justify-end pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowCreateModal(false)}
                  disabled={creatingTemplate}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateRole}
                  disabled={creatingTemplate}
                >
                  {creatingTemplate ? "Creating..." : "Create Role"}
                </Button>
              </div>
            </div>
          </SimpleModal>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRoles.map(role => {
            const userCount = getUserCount(role.id);
            return (
              <div key={role.id} className="border rounded-lg p-4 bg-white hover:shadow-md transition">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">{role.name}</h3>
                    <p className="text-xs text-gray-600 mt-1">{role.description}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t">
                  <span className="text-xs text-gray-500">{userCount} user{userCount !== 1 ? 's' : ''}</span>
                  <button
                    onClick={() => setEditingTemplateId(role.id)}
                    className="text-blue-600 hover:text-blue-700 text-sm font-medium"
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
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function UsersAndAccessControl() {
  const [activeTab, setActiveTab] = useState("users");
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
      const [usersRes, rolesRes, modulesRes] = await Promise.all([
        getAllUsers(),
        listRoles(),
        getModulesAndVerbs()
      ]);

      setUsers(Array.isArray(usersRes) ? usersRes : []);
      setRoles(Array.isArray(rolesRes) ? rolesRes : []);
      setModules(modulesRes?.modules || []);

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
      toast.error("Failed to load configuration.");
    } finally {
      setLoading(false);
    }
  };

  const tabClasses = "px-4 py-2 font-medium border-b-2 transition";
  const activeTabClasses = "border-blue-600 text-blue-600";
  const inactiveTabClasses = "border-transparent text-gray-600 hover:text-gray-900";

  return (
    <div className="mx-auto max-w-7xl p-6">
      <Card title="Users & Access Control">
        {/* Tab Navigation */}
        <div className="flex gap-6 mb-6 border-b">
          <button
            onClick={() => setActiveTab("users")}
            className={`${tabClasses} ${activeTab === "users" ? activeTabClasses : inactiveTabClasses}`}
          >
            👥 Users
          </button>
          <button
            onClick={() => setActiveTab("templates")}
            className={`${tabClasses} ${activeTab === "templates" ? activeTabClasses : inactiveTabClasses}`}
          >
            📋 Role Templates
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === "users" && (
          <UsersSection
            loading={loading}
            error={error}
            users={users}
            roles={roles}
            currentUserPermissions={currentUserPermissions}
          />
        )}
        {activeTab === "templates" && (
          <RoleTemplatesSection
            loading={loading}
            error={error}
            modules={modules}
            roles={roles}
            users={users}
          />
        )}
      </Card>
    </div>
  );
}
