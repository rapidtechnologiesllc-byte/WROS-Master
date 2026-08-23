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

  const [partners, setPartners] = useState([
    { id: 1, name: "Partner 1" },
    { id: 2, name: "Partner 2" },
    { id: 3, name: "Partner 3" }
  ]);

  const [jobTitles, setJobTitles] = useState([]);

  const ORG_LEVEL_ROLES = ["CEO", "CFO", "Admin", "Finance"]; // No BU restriction

  const [createForm, setCreateForm] = useState({
    user_name: "",
    job_title: "",
    user_email: "",
    user_password: "",
    user_role: roles[0]?.name || "",
    business_unit_id: "",
    partner_id: "",
    role_ids: [] // Multi-role support
  });

  const [editForm, setEditForm] = useState({
    user_name: "",
    job_title: "",
    user_role: "",
    business_unit_id: "",
    partner_id: "",
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

  // Load job titles from database (via API)
  const loadJobTitles = async () => {
    try {
      const { data } = await apiRequest("/hr/job-titles", {
        method: "GET"
      });
      const titles = Array.isArray(data?.job_titles) ? data.job_titles : [];
      setJobTitles(titles);
    } catch (err) {
      console.error("Failed to load job titles:", err);
      // If API fails, use empty list (user can still type or fallback to defaults)
      setJobTitles([]);
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

  // Load job titles and business units when modals open
  useEffect(() => {
    if (showCreateModal || showEditModal) {
      loadJobTitles();
      loadBusinessUnits();
    }
  }, [showCreateModal, showEditModal]);

  const selectedUser = users.find(u => u.user_id === selectedUserId);

  const handleCreate = async () => {
    // Validate all required fields
    if (!createForm.user_name.trim()) {
      toast.error("User name is required.");
      return;
    }
    if (!createForm.user_email.trim()) {
      toast.error("Email is required.");
      return;
    }
    if (!createForm.user_password.trim()) {
      toast.error("Password is required.");
      return;
    }
    if (!createForm.job_title.trim()) {
      toast.error("Job Title is required.");
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

      // Include partner if selected
      if (createForm.partner_id) {
        payload.partner_id = parseInt(createForm.partner_id, 10);
      }

      // Use new multi-role endpoint when roles are selected
      if (roleIds.length > 0) {
        console.debug("[CREATE USER] Payload being sent:", payload);
        console.debug("[CREATE USER] Stringified payload:", JSON.stringify(payload));
        const response = await apiRequest("/hr/users/create-with-roles", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        console.debug("[CREATE USER] Response:", response);
      }

      toast.success("User created successfully.");
      setShowCreateModal(false);
      setCreateForm({ user_name: "", job_title: "", user_email: "", user_password: "", user_role: roles[0]?.name || "", business_unit_id: "", partner_id: "", role_ids: [] });
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

      // Include partner if selected
      if (editForm.partner_id) {
        payload.partner_id = parseInt(editForm.partner_id, 10);
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
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Job Title</label>
            <select
              value={createForm.job_title || ""}
              onChange={(e) => setCreateForm({ ...createForm, job_title: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a job title...</option>
              {jobTitles.length > 0 ? (
                jobTitles.map(title => (
                  <option key={title.id} value={title.name}>{title.name}</option>
                ))
              ) : (
                <option disabled>Loading job titles...</option>
              )}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Partner</label>
            <select
              value={createForm.partner_id || ""}
              onChange={(e) => setCreateForm({ ...createForm, partner_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a partner...</option>
              {partners.map(partner => (
                <option key={partner.id} value={partner.id}>{partner.name}</option>
              ))}
            </select>
          </div>

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
              {roles.filter(role => (role.name !== "Super User" || role.id) && (role.is_active !== false)).map(role => {
                const isOrgLevel = ORG_LEVEL_ROLES.includes(role.name);
                return (
                  <option key={role.id} value={role.id}>
                    {role.name} {isOrgLevel ? "(Org-level)" : ""}
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-gray-500 mt-1">Select a role template from the available options (disabled templates not shown)</p>
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

          {/* Navigation Preview */}
          {createForm.role_ids && createForm.role_ids.length > 0 && (
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-300">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Navigation Preview</h4>
              <p className="text-xs text-gray-600 mb-2">This user will see these menu items:</p>
              <div className="space-y-2">
                {(() => {
                  const selectedRole = roles.find(r => r.id === createForm.role_ids?.[0]);
                  if (!selectedRole) return null;

                  // Simple role-based nav mapping
                  const roleNavMap = {
                    "Admin": ["📊 Dashboard", "👥 Candidates", "💼 Jobs", "👔 Employees", "📋 Admin", "⚙️ Settings"],
                    "Recruiter": ["📊 Dashboard", "👥 Candidates", "💼 Jobs", "📝 Interviews", "📋 Submissions"],
                    "HR Manager": ["📊 Dashboard", "👥 Candidates", "👔 Employees", "📋 Interviews", "📝 Reports"],
                    "Finance": ["💰 Invoices", "💵 Revenue", "📊 Reports", "💼 Finance Operations"],
                    "Partner": ["👥 Candidates", "💼 Sales Pipeline", "👔 Employees", "📊 Dashboard"],
                    "BU Head": ["📊 Dashboard", "👥 Candidates", "👔 Employees", "📋 Reports", "💼 Business Unit Management"],
                    "CEO": ["📊 Dashboard", "👥 Candidates", "💰 Finance", "📊 Executive Reports", "⚙️ Admin", "🏢 Organization"]
                  };

                  const navItems = roleNavMap[selectedRole.name] || ["📊 Dashboard"];

                  return (
                    <ul className="text-xs text-gray-700 space-y-1">
                      {navItems.map((item, idx) => (
                        <li key={idx} className="flex items-center gap-2 p-2 rounded bg-white">
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  );
                })()}
              </div>
              <p className="text-xs text-gray-500 mt-3 italic">Navigation based on "{roles.find(r => r.id === createForm.role_ids?.[0])?.name || "Unknown"}" role template</p>
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
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Job Title</label>
            <select
              value={editForm.job_title || ""}
              onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a job title...</option>
              {jobTitles.length > 0 ? (
                jobTitles.map(title => (
                  <option key={title.id} value={title.name}>{title.name}</option>
                ))
              ) : (
                <option disabled>Loading job titles...</option>
              )}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Partner</label>
            <select
              value={editForm.partner_id || ""}
              onChange={(e) => setEditForm({ ...editForm, partner_id: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a partner...</option>
              {partners.map(partner => (
                <option key={partner.id} value={partner.id}>{partner.name}</option>
              ))}
            </select>
          </div>

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
              {roles.filter(role => (role.name !== "Super User" || role.id) && (role.is_active !== false)).map(role => {
                const isOrgLevel = ORG_LEVEL_ROLES.includes(role.name);
                return (
                  <option key={role.id} value={role.id}>
                    {role.name} {isOrgLevel ? "(Org-level)" : ""}
                  </option>
                );
              })}
            </select>
            <p className="text-xs text-gray-500 mt-1">Select a role template from the available options (disabled templates not shown)</p>
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
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [toggling, setToggling] = useState({});
  const [togglingTemplate, setTogglingTemplate] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createRoleForm, setCreateRoleForm] = useState({ name: "", description: "" });
  const [creatingTemplate, setCreatingTemplate] = useState(false);
  const [expandedModules, setExpandedModules] = useState({});
  const [moduleStates, setModuleStates] = useState({});

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

  // Count users per template
  const getUserCount = (roleId) => {
    return users.filter(u => u.role_id === roleId).length;
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

    setCreatingTemplate(true);
    try {
      await apiRequest("/admin/role-templates", {
        method: "POST",
        body: JSON.stringify({
          name: createRoleForm.name,
          display_name: createRoleForm.name,
          description: createRoleForm.description,
          permissions: []
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
          ? { ...r, is_active: !currentStatus }
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRoles.map(role => {
            const userCount = getUserCount(role.id);
            const isActive = role.is_active !== false; // Default to true if not specified
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
  const [businessUnits, setBusinessUnits] = useState([]);
  const [showAddBUModal, setShowAddBUModal] = useState(false);
  const [newBUName, setNewBUName] = useState("");
  const [newBUDescription, setNewBUDescription] = useState("");
  const [newBURegion, setNewBURegion] = useState("");
  const [newBUContinent, setNewBUContinent] = useState("");
  const [editingBUId, setEditingBUId] = useState(null);
  const [editBUName, setEditBUName] = useState("");
  const [editBUDescription, setEditBUDescription] = useState("");
  const [editBURegion, setEditBURegion] = useState("");
  const [editBUContinent, setEditBUContinent] = useState("");
  const [isSubmittingBU, setIsSubmittingBU] = useState(false);

  useEffect(() => {
    loadBusinessUnits();
  }, []);

  const loadBusinessUnits = async () => {
    try {
      const { data } = await apiRequest("/bu-context/available-buses", {
        skipAuth: true,
        method: "GET"
      });
      const busData = data?.business_units || [];
      setBusinessUnits(busData);
    } catch (err) {
      console.error("Failed to load business units:", err);
      setBusinessUnits([]);
    }
  };

  const handleAddBusinessUnit = async (e) => {
    e.preventDefault();
    if (!newBUName.trim()) {
      toast.error("Business Unit Name is required");
      return;
    }
    setIsSubmittingBU(true);
    try {
      const payload = {
        name: newBUName.trim(),
        description: newBUDescription.trim() || null,
        ...(newBURegion && { region: newBURegion.trim() }),
        ...(newBUContinent && { continent: newBUContinent.trim() }),
      };

      await apiRequest("/rbac/business-units", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      toast.success("Business Unit created successfully");
      loadBusinessUnits();
      setShowAddBUModal(false);
      setNewBUName("");
      setNewBUDescription("");
      setNewBURegion("");
      setNewBUContinent("");
    } catch (err) {
      toast.error(err?.message || "Failed to add business unit");
    } finally {
      setIsSubmittingBU(false);
    }
  };

  const handleEditBusinessUnit = (bu) => {
    setEditingBUId(bu.id);
    setEditBUName(bu.name || "");
    setEditBUDescription(bu.description || "");
    setEditBURegion(bu.region || "");
    setEditBUContinent(bu.continent || "");
  };

  const handleSaveEditedBusinessUnit = async () => {
    if (!editBUName.trim()) {
      toast.error("Business Unit Name is required");
      return;
    }
    setIsSubmittingBU(true);
    try {
      await apiRequest(`/rbac/business-units/${editingBUId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editBUName.trim(),
          description: editBUDescription.trim() || null,
          ...(editBURegion && { region: editBURegion.trim() }),
          ...(editBUContinent && { continent: editBUContinent.trim() }),
        }),
      });
      loadBusinessUnits();
      setEditingBUId(null);
      setEditBUName("");
      setEditBUDescription("");
      setEditBURegion("");
      setEditBUContinent("");
      toast.success("Business Unit updated successfully");
    } catch (err) {
      toast.error(err?.message || "Failed to update business unit");
    } finally {
      setIsSubmittingBU(false);
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
      <button
        onClick={() => setShowAddBUModal(true)}
        className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
      >
        <Plus className="h-4 w-4" /> Add Business Unit
      </button>
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
                onClick={() => handleEditBusinessUnit(bu)}
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

      {showAddBUModal && (
        <SimpleModal isOpen={true} onClose={() => { setShowAddBUModal(false); setNewBUName(""); setNewBUDescription(""); setNewBURegion(""); setNewBUContinent(""); }} title="Add Business Unit">
          <form onSubmit={handleAddBusinessUnit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit Name *</label>
              <input
                type="text"
                value={newBUName}
                onChange={(e) => setNewBUName(e.target.value)}
                placeholder="e.g., Asia Pacific"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                disabled={isSubmittingBU}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={newBUDescription}
                onChange={(e) => setNewBUDescription(e.target.value)}
                placeholder="Add a description..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                rows="3"
                disabled={isSubmittingBU}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
              <input
                type="text"
                value={newBURegion}
                onChange={(e) => setNewBURegion(e.target.value)}
                placeholder="e.g., Asia, Europe, North America"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Continent</label>
              <input
                type="text"
                value={newBUContinent}
                onChange={(e) => setNewBUContinent(e.target.value)}
                placeholder="e.g., Asia, Europe, North America"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => { setShowAddBUModal(false); setNewBUName(""); setNewBUDescription(""); setNewBURegion(""); setNewBUContinent(""); }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                disabled={isSubmittingBU}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={!newBUName.trim() || isSubmittingBU}
              >
                {isSubmittingBU ? "Adding..." : "Add Business Unit"}
              </button>
            </div>
          </form>
        </SimpleModal>
      )}

      {editingBUId && (
        <SimpleModal isOpen={true} onClose={() => setEditingBUId(null)} title="Edit Business Unit">
          <form onSubmit={(e) => { e.preventDefault(); handleSaveEditedBusinessUnit(); }} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit Name *</label>
              <input
                type="text"
                value={editBUName}
                onChange={(e) => setEditBUName(e.target.value)}
                placeholder="e.g., Asia Pacific"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={editBUDescription}
                onChange={(e) => setEditBUDescription(e.target.value)}
                placeholder="Add a description..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                rows="3"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
              <input
                type="text"
                value={editBURegion}
                onChange={(e) => setEditBURegion(e.target.value)}
                placeholder="e.g., Asia, Europe, North America"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Continent</label>
              <input
                type="text"
                value={editBUContinent}
                onChange={(e) => setEditBUContinent(e.target.value)}
                placeholder="e.g., Asia, Europe, North America"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => setEditingBUId(null)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={!editBUName.trim() || isSubmittingBU}
              >
                {isSubmittingBU ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </form>
        </SimpleModal>
      )}
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
  const [isSubmittingOrgNode, setIsSubmittingOrgNode] = useState(false);

  useEffect(() => {
    loadOrgNodes();
    loadBusinessUnits();
  }, []);

  const loadOrgNodes = async () => {
    try {
      const { data } = await apiRequest("/org/nodes");
      setOrgNodes(Array.isArray(data) ? data : data?.org_nodes || []);
    } catch (err) {
      console.error("Failed to load org nodes:", err);
    }
  };

  const loadBusinessUnits = async () => {
    try {
      const { data } = await apiRequest("/bu-context/available-buses", { skipAuth: true });
      setBusinessUnits(data?.business_units || []);
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
      setPositions([...positions, { id: Math.max(...positions.map(p => p.id), 0) + 1, name: newPositionName }]);
      setNewPositionName("");
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
    setEditOrgNodePosition(node.position_id.toString());
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
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowAddPositionModal(false)}
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
  const [deliveryCenters, setDeliveryCenters] = useState([
    { id: 1, name: "Austin, TX", type: "HQ", buServed: ["North America"], headcount: 150, city: "Austin", country: "USA" },
    { id: 2, name: "Youngstown, OH", type: "Delivery", buServed: ["North America"], headcount: 300, city: "Youngstown", country: "USA" },
  ]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingDCId, setEditingDCId] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    type: "Delivery",
    city: "",
    country: "",
    headcount: 0
  });

  const resetForm = () => {
    setFormData({ name: "", type: "Delivery", city: "", country: "", headcount: 0 });
  };

  const handleAdd = () => {
    if (!formData.name.trim()) {
      toast.error("Delivery Center name is required");
      return;
    }
    const newDC = {
      id: Math.max(...deliveryCenters.map(dc => dc.id), 0) + 1,
      name: formData.name,
      type: formData.type,
      buServed: ["North America"],
      headcount: formData.headcount,
      city: formData.city,
      country: formData.country
    };
    setDeliveryCenters([...deliveryCenters, newDC]);
    resetForm();
    setShowAddModal(false);
    toast.success("Delivery Center added successfully");
  };

  const handleEdit = (dc) => {
    setEditingDCId(dc.id);
    setFormData({
      name: dc.name,
      type: dc.type,
      city: dc.city || "",
      country: dc.country || "",
      headcount: dc.headcount
    });
  };

  const handleSaveEdit = () => {
    if (!formData.name.trim()) {
      toast.error("Delivery Center name is required");
      return;
    }
    setDeliveryCenters(deliveryCenters.map(dc =>
      dc.id === editingDCId
        ? { ...dc, name: formData.name, type: formData.type, city: formData.city, country: formData.country, headcount: formData.headcount }
        : dc
    ));
    resetForm();
    setEditingDCId(null);
    toast.success("Delivery Center updated successfully");
  };

  const handleDelete = (dcId) => {
    if (window.confirm("Are you sure you want to delete this delivery center?")) {
      setDeliveryCenters(deliveryCenters.filter(dc => dc.id !== dcId));
      toast.success("Delivery Center deleted");
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={() => { resetForm(); setShowAddModal(true); }}
        className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium"
      >
        <Plus className="h-4 w-4" /> Add Delivery Center
      </button>
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

      {showAddModal && (
        <SimpleModal isOpen={true} onClose={() => { setShowAddModal(false); resetForm(); }} title="Add Delivery Center">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Center Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Mumbai, India"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="Delivery">Delivery Center</option>
                <option value="HQ">Headquarters</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <input
                  type="text"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="City"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                <input
                  type="text"
                  value={formData.country}
                  onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                  placeholder="Country"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Headcount</label>
              <input
                type="number"
                value={formData.headcount}
                onChange={(e) => setFormData({ ...formData, headcount: parseInt(e.target.value) || 0 })}
                placeholder="Number of employees"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => { setShowAddModal(false); resetForm(); }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={!formData.name.trim()}
              >
                Add Delivery Center
              </button>
            </div>
          </div>
        </SimpleModal>
      )}

      {editingDCId && (
        <SimpleModal isOpen={true} onClose={() => { setEditingDCId(null); resetForm(); }} title="Edit Delivery Center">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Center Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Mumbai, India"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              >
                <option value="Delivery">Delivery Center</option>
                <option value="HQ">Headquarters</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <input
                  type="text"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="City"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
                <input
                  type="text"
                  value={formData.country}
                  onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                  placeholder="Country"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Headcount</label>
              <input
                type="number"
                value={formData.headcount}
                onChange={(e) => setFormData({ ...formData, headcount: parseInt(e.target.value) || 0 })}
                placeholder="Number of employees"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button
                type="button"
                onClick={() => { setEditingDCId(null); resetForm(); }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                disabled={!formData.name.trim()}
              >
                Save Changes
              </button>
            </div>
          </div>
        </SimpleModal>
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
