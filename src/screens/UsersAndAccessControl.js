// Users & Access Control Management
// Unified HubSpot-style screen combining: User Management, RBAC, Roles, Permissions
// Left sidebar: Categories (Users, Roles, Permissions)
// Right side: Content for selected category

import React, { useEffect, useMemo, useState } from "react";
import {
  Plus, Edit2, Trash2, Lock, Search, AlertCircle, CheckCircle2,
  ChevronDown, Copy, Eye
} from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { toast } from "react-toastify";
import {
  getAllUsers,
  createHrUser,
  updateHrUser,
  deleteHrUser,
  changeHrMePassword,
  getHrMe,
} from "../services/api/users";
import {
  listRoles,
  getModulesAndVerbs,
  getRolesMatrix,
  grantPermission,
  revokePermission,
  assignRoleToUser,
} from "../services/api/rbac";
import { apiRequest } from "../services/api/client";

const CATEGORIES = [
  { key: "users", label: "Users", icon: "👥" },
  { key: "roles", label: "Roles", icon: "🔐" },
  { key: "permissions", label: "Permissions", icon: "🔑" },
];

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

function safeText(v) {
  return v == null ? "" : String(v);
}

// ============================================================================
// USERS SECTION
// ============================================================================

function UsersSection({ loading, error, users, roles }) {
  const [busy, setBusy] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const [createForm, setCreateForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    user_role: roles[0]?.name || ""
  });

  const [editForm, setEditForm] = useState({
    user_name: "",
    user_role: ""
  });

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
    if (!createForm.user_role) {
      toast.error("Role is required.");
      return;
    }

    setBusy(true);
    try {
      await createHrUser({
        user_name: createForm.user_name,
        user_email: createForm.user_email,
        user_password: createForm.user_password,
        user_role: createForm.user_role
      });
      toast.success("User created successfully.");
      setShowCreateModal(false);
      setCreateForm({ user_name: "", user_email: "", user_password: "", user_role: roles[0]?.name || "" });
      // Refresh parent data
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
      await updateHrUser(selectedUserId, {
        user_name: editForm.user_name,
        user_role: editForm.user_role
      });
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
          { header: "Name", accessor: "user_name" },
          { header: "Email", accessor: "user_email" },
          { header: "Role", accessor: "user_role" },
          {
            header: "Actions",
            cell: (row) => (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setSelectedUserId(row.user_id);
                    setEditForm({
                      user_name: safeText(row.user_name),
                      user_role: safeText(row.user_role)
                    });
                    setShowEditModal(true);
                  }}
                  className="text-blue-600 hover:text-blue-700"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => {
                    setSelectedUserId(row.user_id);
                    setShowResetModal(true);
                  }}
                  className="text-amber-600 hover:text-amber-700"
                >
                  <Lock className="h-4 w-4" />
                </button>
                <button
                  onClick={() => {
                    setSelectedUserId(row.user_id);
                    handleDelete();
                  }}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
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
          <Select
            label="Role"
            value={createForm.user_role}
            onChange={(e) => setCreateForm({ ...createForm, user_role: e.target.value })}
            options={roles.map(r => ({ label: r.name, value: r.name }))}
          />
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

      {/* Edit User Modal */}
      <SimpleModal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="Edit User"
      >
        <div className="space-y-4">
          <Input
            label="Name"
            value={editForm.user_name}
            onChange={(e) => setEditForm({ ...editForm, user_name: e.target.value })}
          />
          <Select
            label="Role"
            value={editForm.user_role}
            onChange={(e) => setEditForm({ ...editForm, user_role: e.target.value })}
            options={roles.map(r => ({ label: r.name, value: r.name }))}
          />
          <div className="flex gap-3 justify-end pt-4">
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
          <p className="text-sm text-gray-600">
            Reset password for: <strong>{selectedUser?.user_name}</strong>
          </p>
          <Input
            label="New Password"
            type="password"
            placeholder="••••••••"
            value={resetForm.new_password}
            onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })}
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
    </div>
  );
}

// ============================================================================
// ROLES SECTION
// ============================================================================

function RolesSection({ loading, error, roles }) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredRoles = useMemo(() => {
    if (!searchTerm) return roles;
    const term = searchTerm.toLowerCase();
    return roles.filter(r =>
      (r.name || "").toLowerCase().includes(term) ||
      (r.description || "").toLowerCase().includes(term)
    );
  }, [roles, searchTerm]);

  if (loading) return <div className="p-6 text-gray-500">Loading roles...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <Input
        placeholder="Search roles..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="max-w-xs"
      />

      <div className="grid gap-4">
        {filteredRoles.map((role) => (
          <Card key={role.id} className="p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm font-semibold text-gray-900">{role.name}</div>
                <div className="mt-1 text-xs text-gray-500">{role.description}</div>
              </div>
              <div className="text-xs text-gray-400">ID: {role.id}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// PERMISSIONS SECTION
// ============================================================================

function PermissionsSection({ loading, error, modules, roles, verbMatrix }) {
  const [selectedRole, setSelectedRole] = useState(roles[0]?.id || "");
  const [searchTerm, setSearchTerm] = useState("");
  const [toggling, setToggling] = useState({});

  const filteredModules = useMemo(() => {
    if (!searchTerm) return modules;
    const term = searchTerm.toLowerCase();
    return modules.filter(m =>
      (m.name || "").toLowerCase().includes(term)
    );
  }, [modules, searchTerm]);

  const currentRole = roles.find(r => r.id === selectedRole);
  const currentPermissions = currentRole?.permissions || {};

  const handleTogglePermission = async (module, verb, currentState) => {
    const key = `${selectedRole}_${module}_${verb}`;
    setToggling({ ...toggling, [key]: true });

    try {
      if (currentState) {
        await revokePermission(selectedRole, module, verb);
      } else {
        await grantPermission(selectedRole, module, verb);
      }
      toast.success("Permission updated.");
      window.location.reload();
    } catch (err) {
      toast.error(err.message || "Failed to update permission.");
    } finally {
      setToggling({ ...toggling, [key]: false });
    }
  };

  if (loading) return <div className="p-6 text-gray-500">Loading permissions...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <Select
        label="Select Role"
        value={selectedRole}
        onChange={(e) => setSelectedRole(e.target.value)}
        options={roles.map(r => ({ label: r.name, value: r.id }))}
      />

      <Input
        placeholder="Search modules..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="max-w-xs"
      />

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="px-4 py-2 text-left font-semibold">Module</th>
              {Object.keys(verbMatrix).flatMap(m => Object.keys(verbMatrix[m] || {})).filter((v, i, a) => a.indexOf(v) === i).map(verb => (
                <th key={verb} className="px-4 py-2 text-center font-semibold text-xs">{verb}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredModules.map(module => (
              <tr key={module.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{module.name}</td>
                {Object.keys(verbMatrix[module.name] || {}).map(verb => {
                  const key = `${selectedRole}_${module.name}_${verb}`;
                  const hasPermission = currentPermissions[module.name]?.[verb] || false;
                  const isToggling = toggling[key];
                  return (
                    <td key={verb} className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleTogglePermission(module.name, verb, hasPermission)}
                        disabled={isToggling}
                        className={`inline-flex items-center justify-center h-6 w-6 rounded ${
                          hasPermission
                            ? "bg-green-100 text-green-600 hover:bg-green-200"
                            : "bg-gray-100 text-gray-400 hover:bg-gray-200"
                        }`}
                      >
                        {hasPermission ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function UsersAndAccessControl() {
  const [activeCategory, setActiveCategory] = useState("users");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [verbMatrix, setVerbMatrix] = useState({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [usersRes, rolesRes, matrixRes] = await Promise.all([
        getAllUsers(),
        listRoles(),
        getModulesAndVerbs()
      ]);

      setUsers(Array.isArray(usersRes) ? usersRes : []);
      setRoles(Array.isArray(rolesRes) ? rolesRes : []);
      setModules(matrixRes.modules || []);
      setVerbMatrix(matrixRes.verb_matrix || {});
    } catch (err) {
      setError(err.message || "Failed to load data.");
      toast.error("Failed to load configuration.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-7xl gap-6 p-6">
      {/* Left Sidebar */}
      <aside className="w-52 shrink-0">
        <nav className="space-y-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveCategory(cat.key)}
              className={`block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                activeCategory === cat.key
                  ? "bg-bx-orange/10 text-bx-orange"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <span className="mr-2">{cat.icon}</span>
              {cat.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Right Content */}
      <main className="min-w-0 flex-1">
        <Card title={CATEGORIES.find(c => c.key === activeCategory)?.label}>
          {activeCategory === "users" && (
            <UsersSection
              loading={loading}
              error={error}
              users={users}
              roles={roles}
            />
          )}
          {activeCategory === "roles" && (
            <RolesSection
              loading={loading}
              error={error}
              roles={roles}
            />
          )}
          {activeCategory === "permissions" && (
            <PermissionsSection
              loading={loading}
              error={error}
              modules={modules}
              roles={roles}
              verbMatrix={verbMatrix}
            />
          )}
        </Card>
      </main>
    </div>
  );
}
