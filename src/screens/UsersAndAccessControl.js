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
  listRoleTemplates,
  listModulesAndResources,
  grantPermission,
  revokePermission,
  getRoleTemplate
} from "../services/api/role_templates";
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

function UsersSection({ loading, error, users, roles, currentUserPermissions = {} }) {
  const [busy, setBusy] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const [businessUnits, setBusinessUnits] = useState([
    { id: 1, name: "North America", bu_name: "North America" },
    { id: 2, name: "Europe", bu_name: "Europe" },
    { id: 3, name: "Asia Pacific", bu_name: "Asia Pacific" }
  ]);

  const ORG_LEVEL_ROLES = ["CEO", "CFO", "Admin", "Finance"]; // No BU restriction

  const [createForm, setCreateForm] = useState({
    user_name: "",
    job_title: "",
    user_email: "",
    user_password: "",
    user_role: roles[0]?.name || "",
    business_unit_id: "",
    role_ids: [] // Multi-role support
  });

  const [editForm, setEditForm] = useState({
    user_name: "",
    job_title: "",
    user_role: "",
    business_unit_id: "",
    role_ids: [], // Multi-role support for edit
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

  // Load business units on demand (when modal opens)
  const loadBusinessUnits = async () => {
    try {
      // Try the RBAC endpoint first
      const { data } = await apiRequest("/rbac/business-units", {
        method: "GET"
      });
      const busData = Array.isArray(data) ? data : (data?.business_units || data?.data || []);
      setBusinessUnits(busData);
    } catch (err) {
      console.error("Failed to load business units from /rbac/business-units:", err);
      try {
        // Fallback: try legacy endpoint
        const { data } = await apiRequest("/business-units", {
          method: "GET"
        });
        const busData = Array.isArray(data) ? data : (data?.business_units || data?.data || []);
        setBusinessUnits(busData);
      } catch (fallbackErr) {
        console.error("Fallback also failed, using default business units:", fallbackErr);
        // Fallback: set some default business units
        setBusinessUnits([
          { id: 1, name: "North America", bu_name: "North America" },
          { id: 2, name: "Europe", bu_name: "Europe" },
          { id: 3, name: "Asia Pacific", bu_name: "Asia Pacific" }
        ]);
      }
    }
  };

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

    // Check if any selected roles are BU-scoped (not org-level)
    const selectedRoles = roleIds.map(id => roles.find(r => r.id === id)).filter(Boolean);
    const hasOrgLevelRole = selectedRoles.some(r => ORG_LEVEL_ROLES.includes(r.name));
    const hasBUScopedRole = selectedRoles.some(r => !ORG_LEVEL_ROLES.includes(r.name));

    // Validate BU requirement based on role type
    if (hasBUScopedRole && !createForm.business_unit_id) {
      toast.error("Business Unit is required for BU-scoped roles.");
      return;
    }

    setBusy(true);
    try {
      const payload = {
        user_name: createForm.user_name,
        user_email: createForm.user_email,
        user_password: createForm.user_password,
        job_title: createForm.job_title || "",
        role_ids: roleIds.map(id => parseInt(id, 10))
      };

      // Only include BU if it's not an org-level-only user
      if (!hasOrgLevelRole && createForm.business_unit_id) {
        payload.business_unit_id = parseInt(createForm.business_unit_id, 10);
      }

      // Use new multi-role endpoint when roles are selected
      if (roleIds.length > 0) {
        await apiRequest("/hr/users/create-with-roles", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }

      toast.success("User created successfully.");
      setShowCreateModal(false);
      setCreateForm({ user_name: "", job_title: "", user_email: "", user_password: "", user_role: roles[0]?.name || "", business_unit_id: "", role_ids: [] });
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

    // Support both multi-role (new) and single role (legacy) modes
    const roleIds = editForm.role_ids?.length > 0 ? editForm.role_ids :
                    (editForm.user_role ? [roles.find(r => r.name === editForm.user_role)?.id].filter(Boolean) : []);

    if (roleIds.length === 0) {
      toast.error("At least one role is required.");
      return;
    }

    // Check if any selected roles are BU-scoped (not org-level)
    const selectedRoles = roleIds.map(id => roles.find(r => r.id === id)).filter(Boolean);
    const hasOrgLevelRole = selectedRoles.some(r => ORG_LEVEL_ROLES.includes(r.name));
    const hasBUScopedRole = selectedRoles.some(r => !ORG_LEVEL_ROLES.includes(r.name));

    // Validate BU requirement based on role type
    if (hasBUScopedRole && !editForm.business_unit_id) {
      toast.error("Business Unit is required for BU-scoped roles.");
      return;
    }

    setBusy(true);
    try {
      const payload = {
        user_name: editForm.user_name,
        job_title: editForm.job_title || "",
        role_ids: roleIds.map(id => parseInt(id, 10)),
        assigned_at: new Date().toISOString()
      };

      // Only include BU if it's not an org-level-only user
      if (!hasOrgLevelRole && editForm.business_unit_id) {
        payload.business_unit_id = parseInt(editForm.business_unit_id, 10);
      }

      // Use new multi-role endpoint
      if (roleIds.length > 0) {
        await apiRequest(`/hr/users/${selectedUserId}/update-with-roles`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
      }

      // Note: Permission overrides endpoint not yet implemented in backend
      // Skip permission overrides for now - role-based permissions are sufficient
      // TODO: Implement /rbac/users/{userId}/permissions PATCH endpoint if needed

      toast.success("User updated successfully.");
      setShowEditModal(false);

      // If current user was updated, clear localStorage to force refresh of role/permissions
      const currentUserId = localStorage.getItem("hrms_user_id");
      if (currentUserId === selectedUserId) {
        localStorage.removeItem("hrms_roles");
        localStorage.removeItem("hrms_permissions");
        localStorage.removeItem("hrms_business_unit_id");
        localStorage.removeItem("hrms_business_unit_name");
      }

      window.location.reload();
    } catch (err) {
      console.error("Failed to update user:", err);
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
          onChange={(val) => setSearchTerm(val)}
          className="max-w-xs"
        />
        <Button
          onClick={async () => {
            await loadBusinessUnits();
            setShowCreateModal(true);
          }}
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
                      // Load business units on demand
                      await loadBusinessUnits();
                      try {
                        // Fetch user's assigned roles from the new endpoint
                        const userRoles = await apiRequest(`/rbac/users/${row.user_id}/roles`, {
                          method: "GET"
                        });
                        const roleIds = (userRoles?.data?.roles || []).map(r => r.id);

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
                          job_title: row.job_title || "",
                          user_role: safeText(row.user_role),
                          business_unit_id: row.business_unit_id || "",
                          role_ids: roleIds,
                          ...defaultPermissions,
                          ...savedPermissions
                        });
                      } catch (err) {
                        console.error("Failed to fetch user roles or permissions:", err);
                        // Fallback: start with empty role_ids so user can select new roles
                        setEditForm({
                          user_name: safeText(row.user_name),
                          job_title: row.job_title || "",
                          user_role: safeText(row.user_role),
                          business_unit_id: row.business_unit_id || "",
                          role_ids: [],
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
            onChange={(val) => setCreateForm({ ...createForm, user_name: val })}
          />
          <Input
            label="Job Title"
            placeholder="e.g., Recruiter, HR Manager, CEO"
            value={createForm.job_title || ""}
            onChange={(val) => setCreateForm({ ...createForm, job_title: val })}
          />
          <Input
            label="Email"
            type="email"
            placeholder="john@example.com"
            value={createForm.user_email}
            onChange={(val) => setCreateForm({ ...createForm, user_email: val })}
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={createForm.user_password}
            onChange={(val) => setCreateForm({ ...createForm, user_password: val })}
          />

          {/* Role Template Selection (required) - Dropdown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Role Template *</label>
            <select
              value={createForm.role_ids?.[0] || ""}
              onChange={(e) => {
                const roleId = e.target.value ? parseInt(e.target.value, 10) : null;
                setCreateForm({ ...createForm, role_ids: roleId ? [roleId] : [] });
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">Select a role template...</option>
              {roles.filter(role => role.name !== "Super User" || role.id).map(role => {
                const isOrgLevel = ORG_LEVEL_ROLES.includes(role.name);
                return (
                  <option key={role.id} value={role.id}>
                    {role.name} {isOrgLevel ? "(Org-level)" : ""}
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-gray-500 mt-1">Select a role template from the available options</p>
          </div>

          {/* Business Unit Selection (conditional) */}
          {createForm.role_ids && createForm.role_ids.length > 0 &&
           !createForm.role_ids.some(id => {
             const role = roles.find(r => r.id === id);
             return ORG_LEVEL_ROLES.includes(role?.name);
           }) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Business Unit *</label>
              <select
                value={createForm.business_unit_id}
                onChange={(e) => setCreateForm({ ...createForm, business_unit_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select a business unit...</option>
                {businessUnits.map(bu => (
                  <option key={bu.id} value={bu.id}>
                    {bu.bu_name || bu.name || `BU ${bu.id}`}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">Required for BU-scoped roles</p>
            </div>
          )}

          {/* Org-level access indicator */}
          {createForm.role_ids && createForm.role_ids.length > 0 &&
           createForm.role_ids.some(id => {
             const role = roles.find(r => r.id === id);
             return ORG_LEVEL_ROLES.includes(role?.name);
           }) && (
            <div className="p-3 bg-blue-50 text-sm text-blue-700 rounded border border-blue-200">
              ✓ This user will have <strong>organization-wide access</strong> (no Business Unit restriction)
            </div>
          )}
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
            onChange={(val) => setEditForm({ ...editForm, user_name: val })}
          />
          <Input
            label="Job Title"
            placeholder="e.g., Recruiter, HR Manager, CEO"
            value={editForm.job_title || ""}
            onChange={(val) => setEditForm({ ...editForm, job_title: val })}
          />

          {/* Role Template Selection (required) - Dropdown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Role Template *</label>
            <select
              value={editForm.role_ids?.[0] || ""}
              onChange={(e) => {
                const roleId = e.target.value ? parseInt(e.target.value, 10) : null;
                setEditForm({ ...editForm, role_ids: roleId ? [roleId] : [] });
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">Select a role template...</option>
              {roles.filter(role => role.name !== "Super User" || role.id).map(role => {
                const isOrgLevel = ORG_LEVEL_ROLES.includes(role.name);
                return (
                  <option key={role.id} value={role.id}>
                    {role.name} {isOrgLevel ? "(Org-level)" : ""}
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-gray-500 mt-1">Select a role template from the available options</p>
          </div>

          {/* Business Unit Selection (conditional) */}
          {editForm.role_ids && editForm.role_ids.length > 0 &&
           !editForm.role_ids.some(id => {
             const role = roles.find(r => r.id === id);
             return ORG_LEVEL_ROLES.includes(role?.name);
           }) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Business Unit *</label>
              <select
                value={editForm.business_unit_id}
                onChange={(e) => setEditForm({ ...editForm, business_unit_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select a business unit...</option>
                {businessUnits.map(bu => (
                  <option key={bu.id} value={bu.id}>
                    {bu.bu_name || bu.name || `BU ${bu.id}`}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">Required for BU-scoped roles</p>
            </div>
          )}

          {/* Org-level access indicator */}
          {editForm.role_ids && editForm.role_ids.length > 0 &&
           editForm.role_ids.some(id => {
             const role = roles.find(r => r.id === id);
             return ORG_LEVEL_ROLES.includes(role?.name);
           }) && (
            <div className="p-3 bg-blue-50 text-sm text-blue-700 rounded border border-blue-200">
              ✓ This user will have <strong>organization-wide access</strong> (no Business Unit restriction)
            </div>
          )}

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
                      const modules = ["recruitment", "sales", "workforce", "project_management", "finance", "admin"];
                      const expandState = {};
                      modules.forEach(m => {
                        expandState[`expanded_${m}`] = checked;
                      });
                      setEditForm({
                        ...editForm,
                        expandAllPermissions: checked,
                        ...expandState
                      });
                    }}
                  />
                  <span className="text-xs text-gray-700 font-medium">Expand all</span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              {[
                { name: "Recruitment", key: "recruitment", desc: "Candidates, Jobs, Interviews" },
                { name: "Sales", key: "sales", desc: "Client Management, Deals" },
                { name: "Workforce", key: "workforce", desc: "Employees, Timesheets, Projects" },
                { name: "Project Management", key: "project_management", desc: "Projects, Allocations, Resources" },
                { name: "Finance", key: "finance", desc: "Invoices, Reports, Payments" },
                { name: "Admin", key: "admin", desc: "System, Users, Configuration" }
              ].map(module => {
                const expandedKey = `expanded_${module.key}`;
                const isExpanded = editForm.expandAllPermissions || editForm[expandedKey];

                return (
                  <div key={module.key} className="border rounded-lg">
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
                      <div className="flex flex-col items-start gap-0.5">
                        <div className="text-sm font-medium text-gray-900">{module.name}</div>
                        <div className="text-xs text-gray-500">{module.desc}</div>
                      </div>
                      <div className="text-gray-500 text-lg">
                        {isExpanded ? '▼' : '▶'}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="flex flex-wrap gap-3 px-3 py-3 bg-gray-50 border-t">
                        {["view", "create", "edit", "delete"].map(verb => {
                          const permKey = `perm_${module.key}_${verb}`;
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
            onChange={(val) => setResetForm({ new_password: val })}
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

function RoleTemplatesSection({ loading, error, modules, roles, setRoles, users }) {
  const [editingTemplateId, setEditingTemplateId] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [toggling, setToggling] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createRoleForm, setCreateRoleForm] = useState({ name: "", description: "" });
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [expandedModules, setExpandedModules] = useState({});
  const [moduleStates, setModuleStates] = useState({});

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

    setCreatingTemplate(true);
    try {
      await apiRequest("/admin/role-templates", {
        method: "POST",
        body: JSON.stringify({
          name: createRoleForm.name,
          display_name: createRoleForm.name,
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
          onChange={(val) => setSearchTerm(val)}
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

          <div className="border rounded-lg bg-white">
            <div className="bg-gray-50 p-4 border-b">
              <p className="font-medium text-gray-900 mb-1">Module & Resource Permissions</p>
              <p className="text-xs text-gray-600">✓ = Enabled | ○ = Disabled</p>
            </div>

            <div className="divide-y max-h-[600px] overflow-y-auto">
              {Array.isArray(modules) && modules.length > 0 ? (
                modules.map((module, moduleIdx) => {
                  const moduleName = typeof module === 'string' ? module : module.name;
                  const moduleObj = typeof module === 'object' ? module : null;
                  const resources = moduleObj?.resources || [];

                  // For Recruitment module, show all 11 resources
                  const displayResources = moduleName === 'Recruitment'
                    ? [
                        { id: 7, name: 'candidates', display: 'Candidates' },
                        { id: 8, name: 'jobs', display: 'Jobs' },
                        { id: 9, name: 'submissions', display: 'Submissions' },
                        { id: 10, name: 'interviews', display: 'Interviews' },
                        { id: 11, name: 'offers', display: 'Offer Letters' },
                        { id: 12, name: 'intervention_queue', display: 'Intervention Queue' },
                        { id: 13, name: 'rehire_approvals', display: 'Rehire Approval' },
                        { id: 14, name: 'risk_dashboard', display: 'Risk Dashboard' },
                        { id: 15, name: 'thunder_analytics', display: 'Thunder Analytics' },
                        { id: 16, name: 'bulk_launch', display: 'Bulk Launch' },
                        { id: 17, name: 'thunder_chat', display: 'Thunder Chat' }
                      ]
                    : resources;

                  return (
                    <div key={`module_${moduleIdx}`}>
                      <div className="bg-blue-50 px-4 py-3 border-b flex items-center justify-between">
                        <button
                          onClick={() => setExpandedModules(prev => ({
                            ...prev,
                            [moduleName]: !prev[moduleName]
                          }))}
                          className="flex-1 flex items-center gap-3 text-left hover:bg-blue-100 px-2 py-1 rounded transition-colors"
                        >
                          <span className="text-gray-600">
                            {expandedModules[moduleName] ? '▼' : '▶'}
                          </span>
                          <h4 className="font-semibold text-gray-900 capitalize">{moduleName.replace(/_/g, ' ')}</h4>
                        </button>

                        <div className="flex gap-2 items-center ml-auto">
                          <button
                            onClick={() => handleToggleModule(moduleName, displayResources, true)}
                            disabled={toggling[moduleName]}
                            className={`px-3 py-1 rounded text-sm font-semibold transition ${
                              moduleStates[moduleName]?.enabled
                                ? 'bg-green-500 text-white'
                                : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
                            }`}
                          >
                            ON
                          </button>
                          <button
                            onClick={() => handleToggleModule(moduleName, displayResources, false)}
                            disabled={toggling[moduleName]}
                            className={`px-3 py-1 rounded text-sm font-semibold transition ${
                              !moduleStates[moduleName]?.enabled
                                ? 'bg-red-500 text-white'
                                : 'bg-gray-300 text-gray-700 hover:bg-gray-400'
                            }`}
                          >
                            OFF
                          </button>
                        </div>
                      </div>

                      {expandedModules[moduleName] && (
                      <div className="divide-y">
                        {displayResources.length > 0 ? (
                          displayResources.map(resource => {
                            const resId = resource.id || resource.resource_id;
                            const resName = resource.name || resource.resource_name;
                            const resDisplay = resource.display || resource.display_name || resName;

                            // Look up permissions for this resource in editingPermissions
                            const perms = editingPermissions[resName] || {
                              view: false,
                              create: false,
                              edit: false,
                              delete: false
                            };

                            return (
                              <div key={`res_${resId}`} className="px-4 py-3 hover:bg-gray-50">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-sm font-medium text-gray-900">{resDisplay}</span>
                                </div>

                                <div className="grid grid-cols-4 gap-2">
                                  {['view', 'create', 'edit', 'delete'].map(action => {
                                    const hasPermission = perms[action] || false;
                                    return (
                                      <button
                                        key={action}
                                        onClick={() => handleTogglePermission(resName, action, hasPermission)}
                                        className={`py-1 px-2 rounded text-xs font-semibold transition ${
                                          hasPermission
                                            ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                            : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                                        }`}
                                        title={action.charAt(0).toUpperCase() + action.slice(1)}
                                      >
                                        {hasPermission ? '✓' : '○'} {action.charAt(0).toUpperCase()}
                                      </button>
                                    );
                                  })}
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

  const tabClasses = "px-4 py-2 font-medium border-b-2 transition";
  const activeTabClasses = "border-blue-600 text-blue-600";
  const inactiveTabClasses = "border-transparent text-gray-600 hover:text-gray-900";

  // Check if user has permission to manage role templates (Super User, Admin, CEO)
  const canManageRoleTemplates = currentUserPermissions?.["role.manage"] ||
                                 roles.some(r => r.name?.toLowerCase() === "super user");

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
          {canManageRoleTemplates && (
            <button
              onClick={() => setActiveTab("templates")}
              className={`${tabClasses} ${activeTab === "templates" ? activeTabClasses : inactiveTabClasses}`}
            >
              📋 Role Templates
            </button>
          )}
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
            setRoles={setRoles}
            users={users}
          />
        )}
      </Card>
    </div>
  );
}
