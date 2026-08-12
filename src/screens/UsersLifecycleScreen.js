// Users Lifecycle Management Screen
// Integrated HubSpot-style users management with full lifecycle operations:
// Create, Edit, Terminate, Reinstate, Permissions, Audit Trail
import { useEffect, useMemo, useState } from "react";
import {
  Lock, Plus, UserMinus, Users, ChevronDown, X, AlertCircle,
  Search, Filter, MoreVertical, CheckCircle2, XCircle, Clock,
  Eye, Edit2, Trash2, RotateCcw, LogOut
} from "lucide-react";
import { Button, Card, Input, Select, Table, Modal, Drawer } from "../components/ui";
import { apiRequest } from "../services/api/client";

function safeText(v) {
  return v == null ? "" : String(v);
}

export default function UsersLifecycleScreen() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const [users, setUsers] = useState([]);
  const [rbacRoles, setRbacRoles] = useState([]);

  const [busy, setBusy] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");

  // Modal states
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const [showAuditDrawer, setShowAuditDrawer] = useState(false);
  const [showPermissionModal, setShowPermissionModal] = useState(false);
  const [showTerminateModal, setShowTerminateModal] = useState(false);
  const [showReinstatModal, setShowReinstatModal] = useState(false);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  // Forms
  const [addUserForm, setAddUserForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    role_id: ""
  });

  const [editUserForm, setEditUserForm] = useState({
    user_name: "",
    user_email: ""
  });

  const [permissionForm, setPermissionForm] = useState({
    role_id: ""
  });

  const [terminateForm, setTerminateForm] = useState({
    reason: ""
  });

  const [auditTrail, setAuditTrail] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);

  // Filters & Search
  const filteredUsers = useMemo(() => {
    let result = users;

    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      result = result.filter(
        (u) =>
          (u.user_name || "").toLowerCase().includes(search) ||
          (u.user_email || "").toLowerCase().includes(search)
      );
    }

    if (statusFilter) {
      result = result.filter((u) => u.status.toLowerCase() === statusFilter.toLowerCase());
    }

    if (roleFilter) {
      result = result.filter((u) => (u.role_id || "") === roleFilter);
    }

    return result.sort((a, b) => (a.user_name || "").localeCompare(b.user_name || ""));
  }, [users, searchTerm, statusFilter, roleFilter]);

  // Load data
  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [usersRes, rolesRes] = await Promise.all([
        apiRequest("/rbac/users", { method: "GET" }),
        apiRequest("/rbac/roles", { method: "GET" })
      ]);

      setUsers(Array.isArray(usersRes) ? usersRes : []);
      const nextRoles = Array.isArray(rolesRes) ? rolesRes : [];
      setRbacRoles(nextRoles);

      // Default role
      if (nextRoles.length > 0 && !addUserForm.role_id) {
        setAddUserForm((prev) => ({ ...prev, role_id: String(nextRoles[0].id) }));
      }
    } catch (err) {
      setError(err.message || "Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  // Select user for edit/audit
  useEffect(() => {
    const u = users.find((x) => x.user_id === selectedUserId);
    if (!u) return;

    setSelectedUser(u);
    setEditUserForm({
      user_name: safeText(u.user_name),
      user_email: safeText(u.user_email)
    });
    setPermissionForm({
      role_id: safeText(u.role_id)
    });
  }, [selectedUserId, users]);

  // Open edit drawer
  const handleOpenEdit = (userId) => {
    setSelectedUserId(userId);
    setShowEditDrawer(true);
  };

  // Open audit drawer
  const handleOpenAudit = async (userId) => {
    setSelectedUserId(userId);
    setShowAuditDrawer(true);
    try {
      const trail = await apiRequest(`/rbac/users/${userId}/audit-trail`, { method: "GET" });
      setAuditTrail(trail?.audit_records || []);
    } catch (err) {
      setError("Failed to load audit trail.");
    }
  };

  // Add User
  const handleAddUser = async () => {
    if (!addUserForm.user_name.trim()) return setError("User name is required.");
    if (!addUserForm.user_email.trim()) return setError("User email is required.");
    if (!addUserForm.user_password.trim()) return setError("User password is required.");
    if (!addUserForm.role_id) return setError("Role is required.");

    setBusy(true);
    setError("");
    try {
      // Assuming there's a /hr/users endpoint for creation
      await apiRequest("/hr/users", {
        method: "POST",
        body: JSON.stringify(addUserForm)
      });

      setSuccessMessage("User created successfully!");
      setShowAddUserModal(false);
      setAddUserForm({
        user_name: "",
        user_email: "",
        user_password: "",
        role_id: rbacRoles.length > 0 ? String(rbacRoles[0].id) : ""
      });
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to create user.");
    } finally {
      setBusy(false);
    }
  };

  // Update User
  const handleUpdateUser = async () => {
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/rbac/users/${selectedUserId}`, {
        method: "PUT",
        body: JSON.stringify(editUserForm)
      });

      setSuccessMessage("User updated successfully!");
      setShowEditDrawer(false);
      setSelectedUserId("");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to update user.");
    } finally {
      setBusy(false);
    }
  };

  // Update Permissions
  const handleUpdatePermissions = async () => {
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/rbac/users/${selectedUserId}/permissions`, {
        method: "POST",
        body: JSON.stringify(permissionForm)
      });

      setSuccessMessage("Permissions updated successfully!");
      setShowPermissionModal(false);
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to update permissions.");
    } finally {
      setBusy(false);
    }
  };

  // Terminate User
  const handleTerminateUser = async () => {
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/rbac/users/${selectedUserId}/terminate`, {
        method: "POST",
        body: JSON.stringify(terminateForm)
      });

      setSuccessMessage("User terminated. Tasks redistributed to team members.");
      setShowTerminateModal(false);
      setTerminateForm({ reason: "" });
      setShowEditDrawer(false);
      setSelectedUserId("");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to terminate user.");
    } finally {
      setBusy(false);
    }
  };

  // Reinstate User
  const handleReinstatUser = async () => {
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/rbac/users/${selectedUserId}/reinstate`, {
        method: "POST",
        body: JSON.stringify({})
      });

      setSuccessMessage("User reinstated successfully!");
      setShowReinstatModal(false);
      setShowEditDrawer(false);
      setSelectedUserId("");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to reinstate user.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <Card title="Users" icon={<Users className="h-4 w-4" />}>
        <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
      </Card>
    );
  }

  const roleOptions = rbacRoles.map((r) => ({
    value: String(r.id),
    label: r.name
  }));

  return (
    <div className="grid gap-4">
      {/* Messages */}
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {successMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Header with Actions */}
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Users</h2>
        <Button
          onClick={() => setShowAddUserModal(true)}
          icon={<Plus className="h-4 w-4" />}
          variant="primary"
          size="sm"
        >
          Add User
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Search by name or email</label>
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Status</label>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "", label: "All" },
                { value: "Active", label: "Active" },
                { value: "Terminated", label: "Terminated" }
              ]}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Role</label>
            <Select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              options={[
                { value: "", label: "All" },
                ...roleOptions
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Email</th>
                <th className="px-4 py-2 text-left font-medium">Role</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-left font-medium">Created</th>
                <th className="px-4 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-4 py-8 text-center text-gray-500">
                    No users found
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr
                    key={u.user_id}
                    className="border-b hover:bg-gray-50 cursor-pointer"
                    onClick={() => handleOpenEdit(u.user_id)}
                  >
                    <td className="px-4 py-2 font-medium">{u.user_name}</td>
                    <td className="px-4 py-2 text-gray-600">{u.user_email}</td>
                    <td className="px-4 py-2 text-gray-600">{u.role_name || "—"}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                        u.status === "Active"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}>
                        {u.status === "Active" ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenEdit(u.user_id);
                        }}
                        className="text-gray-500 hover:text-gray-700"
                        title="Edit user"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Add User Modal */}
      {showAddUserModal && (
        <Modal
          title="Add User"
          onClose={() => setShowAddUserModal(false)}
          footer={
            <div className="flex gap-2">
              <Button
                onClick={() => setShowAddUserModal(false)}
                variant="secondary"
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddUser}
                variant="primary"
                loading={busy}
              >
                Create User
              </Button>
            </div>
          }
        >
          <div className="grid gap-3">
            <div>
              <label className="text-sm font-medium mb-1 block">Name</label>
              <Input
                type="text"
                value={addUserForm.user_name}
                onChange={(e) =>
                  setAddUserForm({ ...addUserForm, user_name: e.target.value })
                }
                placeholder="John Doe"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1 block">Email</label>
              <Input
                type="email"
                value={addUserForm.user_email}
                onChange={(e) =>
                  setAddUserForm({ ...addUserForm, user_email: e.target.value })
                }
                placeholder="john@example.com"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1 block">Password</label>
              <Input
                type="password"
                value={addUserForm.user_password}
                onChange={(e) =>
                  setAddUserForm({ ...addUserForm, user_password: e.target.value })
                }
                placeholder="Password (min 8 chars)"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1 block">Role</label>
              <Select
                value={addUserForm.role_id}
                onChange={(e) =>
                  setAddUserForm({ ...addUserForm, role_id: e.target.value })
                }
                options={roleOptions}
              />
            </div>
          </div>
        </Modal>
      )}

      {/* Edit User Drawer */}
      {showEditDrawer && selectedUser && (
        <Drawer
          title={`User: ${selectedUser.user_name}`}
          onClose={() => {
            setShowEditDrawer(false);
            setSelectedUserId("");
          }}
        >
          <div className="grid gap-6">
            {/* Basic Info */}
            <div>
              <h3 className="font-semibold mb-3">Basic Information</h3>
              <div className="grid gap-3">
                <div>
                  <label className="text-sm font-medium mb-1 block">Name</label>
                  <Input
                    type="text"
                    value={editUserForm.user_name}
                    onChange={(e) =>
                      setEditUserForm({
                        ...editUserForm,
                        user_name: e.target.value
                      })
                    }
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-1 block">Email</label>
                  <Input
                    type="email"
                    value={editUserForm.user_email}
                    onChange={(e) =>
                      setEditUserForm({
                        ...editUserForm,
                        user_email: e.target.value
                      })
                    }
                  />
                </div>

                <Button
                  onClick={handleUpdateUser}
                  variant="primary"
                  size="sm"
                  loading={busy}
                >
                  Save Changes
                </Button>
              </div>
            </div>

            {/* Permissions */}
            <div>
              <h3 className="font-semibold mb-3">Permissions</h3>
              <div className="grid gap-3">
                <div>
                  <label className="text-sm font-medium mb-1 block">Role</label>
                  <Select
                    value={permissionForm.role_id}
                    onChange={(e) =>
                      setPermissionForm({
                        ...permissionForm,
                        role_id: e.target.value
                      })
                    }
                    options={roleOptions}
                  />
                </div>

                <Button
                  onClick={() => setShowPermissionModal(true)}
                  variant="secondary"
                  size="sm"
                >
                  Update Permissions
                </Button>
              </div>
            </div>

            {/* Status & Actions */}
            <div>
              <h3 className="font-semibold mb-3">Status & Actions</h3>
              <div className="flex items-center gap-2 mb-4">
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ${
                  selectedUser.status === "Active"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-red-100 text-red-700"
                }`}>
                  {selectedUser.status === "Active" ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  {selectedUser.status}
                </span>
              </div>

              <div className="grid gap-2">
                {selectedUser.status === "Active" ? (
                  <Button
                    onClick={() => setShowTerminateModal(true)}
                    variant="danger"
                    size="sm"
                    icon={<LogOut className="h-4 w-4" />}
                  >
                    Terminate User
                  </Button>
                ) : (
                  <Button
                    onClick={() => setShowReinstatModal(true)}
                    variant="secondary"
                    size="sm"
                    icon={<RotateCcw className="h-4 w-4" />}
                  >
                    Reinstate User
                  </Button>
                )}

                <Button
                  onClick={() => handleOpenAudit(selectedUserId)}
                  variant="secondary"
                  size="sm"
                  icon={<Eye className="h-4 w-4" />}
                >
                  View Audit Trail
                </Button>
              </div>
            </div>
          </div>
        </Drawer>
      )}

      {/* Audit Trail Drawer */}
      {showAuditDrawer && selectedUser && (
        <Drawer
          title={`Audit Trail: ${selectedUser.user_name}`}
          onClose={() => {
            setShowAuditDrawer(false);
            setAuditTrail([]);
          }}
        >
          <div className="space-y-4">
            {auditTrail.length === 0 ? (
              <p className="text-sm text-gray-500">No audit records found.</p>
            ) : (
              <div className="space-y-3">
                {auditTrail.map((record, idx) => (
                  <div key={idx} className="border rounded-lg p-3 text-sm">
                    <div className="flex items-start justify-between mb-2">
                      <span className="font-medium text-gray-900">
                        {record.action.replace(/_/g, " ").toUpperCase()}
                      </span>
                      <span className="text-xs text-gray-500">
                        {record.timestamp
                          ? new Date(record.timestamp).toLocaleString()
                          : "—"}
                      </span>
                    </div>

                    {record.action_by && (
                      <p className="text-xs text-gray-600 mb-1">
                        By: <strong>{record.action_by}</strong>
                      </p>
                    )}

                    {record.old_value && (
                      <p className="text-xs text-gray-600 mb-1">
                        Old: <code className="bg-gray-100 px-1 py-0.5 rounded">{record.old_value}</code>
                      </p>
                    )}

                    {record.new_value && (
                      <p className="text-xs text-gray-600">
                        New: <code className="bg-gray-100 px-1 py-0.5 rounded">{record.new_value}</code>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Drawer>
      )}

      {/* Permission Update Modal */}
      {showPermissionModal && selectedUser && (
        <Modal
          title="Update User Permissions"
          onClose={() => setShowPermissionModal(false)}
          footer={
            <div className="flex gap-2">
              <Button
                onClick={() => setShowPermissionModal(false)}
                variant="secondary"
              >
                Cancel
              </Button>
              <Button
                onClick={handleUpdatePermissions}
                variant="primary"
                loading={busy}
              >
                Update Permissions
              </Button>
            </div>
          }
        >
          <div className="grid gap-3">
            <div>
              <label className="text-sm font-medium mb-1 block">Select Role</label>
              <Select
                value={permissionForm.role_id}
                onChange={(e) =>
                  setPermissionForm({
                    ...permissionForm,
                    role_id: e.target.value
                  })
                }
                options={roleOptions}
              />
            </div>

            <div className="text-xs text-gray-600 bg-blue-50 p-2 rounded">
              Changing the role will update all permissions for this user based on the selected role.
            </div>
          </div>
        </Modal>
      )}

      {/* Terminate Modal */}
      {showTerminateModal && selectedUser && (
        <Modal
          title="Terminate User"
          onClose={() => setShowTerminateModal(false)}
          footer={
            <div className="flex gap-2">
              <Button
                onClick={() => setShowTerminateModal(false)}
                variant="secondary"
              >
                Cancel
              </Button>
              <Button
                onClick={handleTerminateUser}
                variant="danger"
                loading={busy}
              >
                Confirm Termination
              </Button>
            </div>
          }
        >
          <div className="grid gap-3">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
              <strong>Warning:</strong> This will mark the user as terminated and redistribute their active tasks to team members.
            </div>

            <div>
              <label className="text-sm font-medium mb-1 block">Reason (optional)</label>
              <Input
                type="text"
                value={terminateForm.reason}
                onChange={(e) =>
                  setTerminateForm({ ...terminateForm, reason: e.target.value })
                }
                placeholder="Left company, Department change, etc."
              />
            </div>
          </div>
        </Modal>
      )}

      {/* Reinstate Modal */}
      {showReinstatModal && selectedUser && (
        <Modal
          title="Reinstate User"
          onClose={() => setShowReinstatModal(false)}
          footer={
            <div className="flex gap-2">
              <Button
                onClick={() => setShowReinstatModal(false)}
                variant="secondary"
              >
                Cancel
              </Button>
              <Button
                onClick={handleReinstatUser}
                variant="primary"
                loading={busy}
              >
                Reinstate
              </Button>
            </div>
          }
        >
          <div className="grid gap-3">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
              This will reactivate the user. Previously assigned tasks will remain with current assignees.
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
