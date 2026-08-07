// Admin HR user management screen.
import { useEffect, useMemo, useState } from "react";
import { Lock, Plus, UserMinus, Users } from "lucide-react";
import { Button, Card, Input, Select, Table } from "../components/ui";
import {
  changeHrMePassword,
  createHrUser,
  deleteHrUser,
  getAllUsers,
  getHrMe,
  updateHrUser
} from "../services/api/users";
import { listRoles } from "../services/api/rbac";

function safeText(v) {
  return v == null ? "" : String(v);
}

export default function HrUserManagement() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [users, setUsers] = useState([]);
  const [me, setMe] = useState(null);
  const [rbacRoles, setRbacRoles] = useState([]);

  const [busy, setBusy] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");

  const [createForm, setCreateForm] = useState({
    user_name: "",
    user_email: "",
    user_password: "",
    user_role: ""
  });

  const [updateForm, setUpdateForm] = useState({
    user_name: "",
    user_role: ""
  });

  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: ""
  });

  const [adminResetForm, setAdminResetForm] = useState({
    user_id: "",
    new_password: ""
  });

  const userOptions = useMemo(() => {
    return ["", ...users.map((u) => u.user_id)];
  }, [users]);
  const roleOptions = useMemo(() => {
    return ["", ...rbacRoles.map((r) => String(r.name || "").trim()).filter(Boolean)];
  }, [rbacRoles]);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [usersRes, meRes, rolesRes] = await Promise.all([
        getAllUsers(),
        getHrMe(),
        listRoles()
      ]);
      setUsers(Array.isArray(usersRes?.users) ? usersRes.users : []);
      setMe(meRes || null);
      const nextRoles = Array.isArray(rolesRes) ? rolesRes : [];
      setRbacRoles(nextRoles);
      const firstRoleName = String(nextRoles[0]?.name || "").trim();
      if (firstRoleName) {
        setCreateForm((prev) => (prev.user_role ? prev : { ...prev, user_role: firstRoleName }));
        setUpdateForm((prev) => (prev.user_role ? prev : { ...prev, user_role: firstRoleName }));
      }
    } catch (err) {
      setError(err.message || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const u = users.find((x) => x.user_id === selectedUserId);
    if (!u) return;
    setUpdateForm({
      user_name: safeText(u.user_name),
      user_role: safeText(u.user_role) || roleOptions[1] || ""
    });
  }, [selectedUserId, users, roleOptions]);

  const handleCreate = async () => {
    if (!createForm.user_name.trim()) return setError("User name is required.");
    if (!createForm.user_email.trim()) return setError("User email is required.");
    if (!createForm.user_password.trim()) return setError("User password is required.");
    if (!createForm.user_role) return setError("User role is required.");

    setBusy(true);
    setError("");
    try {
      await createHrUser(createForm);
      setCreateForm({
        user_name: "",
        user_email: "",
        user_password: "",
        user_role: roleOptions[1] || ""
      });
      setSelectedUserId("");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to create user.");
    } finally {
      setBusy(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await updateHrUser(selectedUserId, updateForm);
      setSelectedUserId("");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to update user.");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (userId) => {
    if (!window.confirm(`Delete HR user ${userId}?`)) return;
    setBusy(true);
    setError("");
    try {
      await deleteHrUser(userId);
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to delete user.");
    } finally {
      setBusy(false);
    }
  };

  const handleChangePassword = async () => {
    setBusy(true);
    setError("");
    try {
      await changeHrMePassword(passwordForm);
      setPasswordForm({ current_password: "", new_password: "" });
    } catch (err) {
      setError(err.message || "Failed to change password.");
    } finally {
      setBusy(false);
    }
  };

  const handleAdminResetPassword = async () => {
    if (!adminResetForm.user_id) return setError("Please select a user.");
    if (!adminResetForm.new_password.trim()) return setError("New password is required.");

    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/hr/admin/users/${adminResetForm.user_id}/reset-password`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ new_password: adminResetForm.new_password })
        }
      );
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to reset password");
      }
      setAdminResetForm({ user_id: "", new_password: "" });
      setError("Password reset successfully!");
      await refresh();
    } catch (err) {
      setError(err.message || "Failed to reset password.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <Card title="HR / Admin Users" icon={<Users className="h-4 w-4" />}>
        <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <Card title="HR Users Directory" icon={<Users className="h-4 w-4" />}>
        <Table
          columns={[
            { key: "id", header: "User ID" },
            { key: "name", header: "Name" },
            { key: "email", header: "Email" },
            { key: "role", header: "Role" },
            { key: "actions", header: "Actions" }
          ]}
          rows={users.map((u) => ({
            id: u.user_id,
            name: u.user_name || "-",
            email: u.user_email,
            role: u.user_role || "-",
            actions: (
              <div className="flex gap-1">
                <Button
                  variant="secondary"
                  onClick={() => setSelectedUserId(u.user_id)}
                  disabled={busy}
                >
                  Edit
                </Button>
                <Button
                  variant="danger"
                  onClick={() => handleDelete(u.user_id)}
                  disabled={busy}
                  className="whitespace-nowrap"
                >
                  <UserMinus className="h-4 w-4 mr-1" /> Delete
                </Button>
              </div>
            )
          }))}
        />
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Create User" icon={<Plus className="h-4 w-4" />}>
          <div className="grid gap-3">
            <Input
              label="Name"
              value={createForm.user_name}
              onChange={(v) => setCreateForm((f) => ({ ...f, user_name: v }))}
            />
            <Input
              label="Email"
              value={createForm.user_email}
              onChange={(v) => setCreateForm((f) => ({ ...f, user_email: v }))}
            />
            <Input
              label="Password"
              type="password"
              value={createForm.user_password}
              onChange={(v) => setCreateForm((f) => ({ ...f, user_password: v }))}
            />
            <Select
              label="Role"
              value={createForm.user_role}
              onChange={(v) => setCreateForm((f) => ({ ...f, user_role: v }))}
              options={roleOptions}
            />
            <div className="flex justify-end">
              <Button onClick={handleCreate} disabled={busy}>
                Create
              </Button>
            </div>
          </div>
        </Card>

        <Card title="Update User" icon={<Users className="h-4 w-4" />}>
          <div className="grid gap-3">
            <Select
              label="User"
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={userOptions}
            />
            <Input
              label="Name"
              value={updateForm.user_name}
              onChange={(v) => setUpdateForm((f) => ({ ...f, user_name: v }))}
              disabled={!selectedUserId}
            />
            <Select
              label="Role"
              value={updateForm.user_role}
              onChange={(v) => setUpdateForm((f) => ({ ...f, user_role: v }))}
              options={roleOptions}
              disabled={!selectedUserId}
            />
            <div className="flex justify-end">
              <Button onClick={handleUpdate} disabled={busy || !selectedUserId}>
                Update
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Admin: Reset User Password" icon={<Lock className="h-4 w-4" />}>
        <div className="grid gap-3 md:grid-cols-2">
          <Select
            label="Select User"
            value={adminResetForm.user_id}
            onChange={(v) => setAdminResetForm((p) => ({ ...p, user_id: v }))}
            options={userOptions}
          />
          <Input
            label="New Password (no current password needed)"
            type="password"
            value={adminResetForm.new_password}
            onChange={(v) => setAdminResetForm((p) => ({ ...p, new_password: v }))}
          />
          <div className="md:col-span-2 flex justify-end gap-2">
            <div className="text-xs text-gray-500 flex-1">
              Admin can reset any user's password without knowing their current password
            </div>
            <Button onClick={handleAdminResetPassword} disabled={busy}>
              Reset Password
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Change My Password" icon={<Lock className="h-4 w-4" />}>
        <div className="grid gap-3 md:grid-cols-2">
          <Input
            label="Current Password"
            type="password"
            value={passwordForm.current_password}
            onChange={(v) => setPasswordForm((p) => ({ ...p, current_password: v }))}
          />
          <Input
            label="New Password"
            type="password"
            value={passwordForm.new_password}
            onChange={(v) => setPasswordForm((p) => ({ ...p, new_password: v }))}
          />
          <div className="md:col-span-2 flex justify-end gap-2">
            <div className="text-xs text-gray-500 flex-1">
              Logged in as: {me?.user_email || "—"}
            </div>
            <Button onClick={handleChangePassword} disabled={busy}>
              Change Password
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

