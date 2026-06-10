// RBAC settings screen (Admin only).
import { useEffect, useMemo, useState } from "react";
import { Shield } from "lucide-react";
import { Button, Card, Input, Select, StatusBadge } from "../components/ui";
import { getAllUsers } from "../services/api/users";
import {
  assignPermissionToRole,
  assignRoleToUser,
  createBusinessUnit,
  createPermission,
  createDepartment,
  createRole,
  deleteBusinessUnit,
  deletePermission,
  deleteRole,
  getUserBusinessUnit,
  getUserPermissionSummary,
  getUserRole,
  getRoleById,
  listBusinessUnits,
  listPermissions,
  listRoles,
  removePermissionFromRole,
  setBusinessUnitForUser,
  revokeUserRole,
  updateBusinessUnit,
  updateRole,
  departmentList,
  setDepartmentForUser,
} from "../services/api/rbac";
import { toast } from "react-toastify";

export default function RbacSettingsScreen() {
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [users, setUsers] = useState([]);

  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedPermissionId, setSelectedPermissionId] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedUserRoleId, setSelectedUserRoleId] = useState("");
  const [selectedBuId, setSelectedBuId] = useState("");

  const [roleDetail, setRoleDetail] = useState(null);
  const [userPermissionSummary, setUserPermissionSummary] = useState(null);
  const [userRoleDetail, setUserRoleDetail] = useState(null);
  const [userBusinessUnitDetail, setUserBusinessUnitDetail] = useState(null);
  const [userDetailNotice, setUserDetailNotice] = useState("");
  const [userBuUpdateId, setUserBuUpdateId] = useState("");

  const [newRole, setNewRole] = useState({ name: "", description: "" });
  const [newPermission, setNewPermission] = useState({
    name: "",
    description: "",
  });
  const [newBu, setNewBu] = useState({ name: "", description: "" });
  const [editRole, setEditRole] = useState({ name: "", description: "" });
  const [editBu, setEditBu] = useState({ name: "", description: "" });
  const [newDepartment, setNewDepartment] = useState({
    name: "",
    description: "",
  });
  const [userForDept, setUserForDept] = useState("");
  const [department, setDepartment] = useState([]);
  const [selectedDept, setSelectedDept] = useState("");

  const roleOptions = useMemo(() => {
    const rows = roles.map((r) => {
      const id = String(r.id ?? "");
      const name = String(r.name || "").trim();
      const label = name ? `${name} (${id})` : id || "Unnamed role";
      return { value: id, label };
    });
    return [{ value: "", label: "—" }, ...rows];
  }, [roles]);

  const permissionOptions = useMemo(
    () => ["", ...permissions.map((p) => String(p.id))],
    [permissions],
  );

  const userOptions = useMemo(() => {
    const rows = users.map((u) => {
      const id = String(u.user_id ?? "");
      const name = String(u.user_name || "").trim();
      const email = String(u.user_email || "").trim();
      const parts = [];
      if (name) parts.push(name);
      if (email && email !== name) parts.push(email);
      const label = parts.length ? parts.join(" — ") : id || "Unknown user";
      return { value: id, label };
    });
    return [{ value: "", label: "—" }, ...rows];
  }, [users]);

  const buOptions = useMemo(
    () => ["", ...businessUnits.map((b) => String(b.id))],
    [businessUnits],
  );

  const deptOptions = [
    { label: "Please select Department", value: "", disabled: true },
    ...(department?.map((dept) => ({
      label: dept?.name,
      value: dept?.id,
    })) || []),
  ];

  useEffect(() => {
    if (
      selectedRoleId &&
      !roles.some((r) => String(r.id) === String(selectedRoleId))
    ) {
      setSelectedRoleId("");
      setRoleDetail(null);
    }
  }, [roles, selectedRoleId]);

  useEffect(() => {
    if (
      selectedPermissionId &&
      !permissions.some((p) => String(p.id) === String(selectedPermissionId))
    ) {
      setSelectedPermissionId("");
    }
  }, [permissions, selectedPermissionId]);

  useEffect(() => {
    if (
      selectedUserId &&
      !users.some((u) => String(u.user_id) === String(selectedUserId))
    ) {
      setSelectedUserId("");
    }
  }, [users, selectedUserId]);

  useEffect(() => {
    if (
      selectedUserRoleId &&
      !roles.some((r) => String(r.id) === String(selectedUserRoleId))
    ) {
      setSelectedUserRoleId("");
    }
  }, [roles, selectedUserRoleId]);

  useEffect(() => {
    if (
      selectedBuId &&
      !businessUnits.some((b) => String(b.id) === String(selectedBuId))
    ) {
      setSelectedBuId("");
    }
  }, [businessUnits, selectedBuId]);

  const loadAll = async () => {
    setLoading(true);
    setError("");
    try {
      const [rolesRes, permsRes, buRes, usersRes, departmentRes] =
        await Promise.all([
          listRoles(),
          listPermissions(),
          listBusinessUnits(),
          getAllUsers(),
          departmentList(),
        ]);
      setRoles(Array.isArray(rolesRes) ? rolesRes : []);
      setPermissions(Array.isArray(permsRes) ? permsRes : []);
      setBusinessUnits(Array.isArray(buRes) ? buRes : []);
      setUsers(Array.isArray(usersRes?.users) ? usersRes.users : []);
      setDepartment(departmentRes);
    } catch (err) {
      setError(err.message || "Failed to load RBAC data.");
    } finally {
      setLoading(false);
    }
  };

  const refreshRoleDetail = async (roleId) => {
    if (!roleId) {
      setRoleDetail(null);
      return;
    }
    try {
      const detail = await getRoleById(roleId);
      setRoleDetail(detail || null);
    } catch (err) {
      setRoleDetail(null);
      setError(err.message || "Failed to load role details.");
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    refreshRoleDetail(selectedRoleId);
  }, [selectedRoleId]);
  useEffect(() => {
    if (!notice && !error) return;

    const timer = setTimeout(() => {
      setNotice("");
      setError("");
    }, 3000);

    return () => clearTimeout(timer);
  }, [notice, error]);

  useEffect(() => {
    if (!roleDetail) return;
    setEditRole({
      name: roleDetail.name || "",
      description: roleDetail.description || "",
    });
  }, [roleDetail]);

  useEffect(() => {
    if (!selectedBuId) {
      setEditBu({ name: "", description: "" });
      return;
    }
    const bu = businessUnits.find((b) => String(b.id) === String(selectedBuId));
    if (!bu) return;
    setEditBu({ name: bu.name || "", description: bu.description || "" });
  }, [selectedBuId, businessUnits]);

  if (loading) {
    return (
      <Card title="RBAC Settings" icon={<Shield className="h-4 w-4" />}>
        <div className="py-4 text-center text-sm text-gray-500">Loading…</div>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <Card title="RBAC Settings" icon={<Shield className="h-4 w-4" />}>
        {error ? (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">Create Role</div>
            <Input
              label="Role name"
              value={newRole.name}
              onChange={(v) => setNewRole((r) => ({ ...r, name: v }))}
            />
            <Input
              label="Description"
              value={newRole.description}
              onChange={(v) => setNewRole((r) => ({ ...r, description: v }))}
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await createRole(newRole);
                    setNewRole({ name: "", description: "" });
                    await loadAll();
                    setNotice("Role created.");
                  } catch (err) {
                    setError(err.message || "Failed to create role.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !newRole.name.trim()}
              >
                Create Role
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">Create Permission</div>
            <Input
              label="Permission name (e.g. candidate.view)"
              value={newPermission.name}
              onChange={(v) => setNewPermission((p) => ({ ...p, name: v }))}
            />
            <Input
              label="Description"
              value={newPermission.description}
              onChange={(v) =>
                setNewPermission((p) => ({ ...p, description: v }))
              }
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await createPermission(newPermission);
                    setNewPermission({ name: "", description: "" });
                    await loadAll();
                    setNotice("Permission created.");
                  } catch (err) {
                    setError(err.message || "Failed to create permission.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !newPermission.name.trim()}
              >
                Create Permission
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Create Business Unit
            </div>
            <Input
              label="Business unit name"
              value={newBu.name}
              onChange={(v) => setNewBu((b) => ({ ...b, name: v }))}
            />
            <Input
              label="Description"
              value={newBu.description}
              onChange={(v) => setNewBu((b) => ({ ...b, description: v }))}
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await createBusinessUnit(newBu);
                    setNewBu({ name: "", description: "" });
                    await loadAll();
                    setNotice("Business unit created.");
                  } catch (err) {
                    setError(err.message || "Failed to create business unit.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !newBu.name.trim()}
              >
                Create Business Unit
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">Create Department</div>

            <Input
              label="Department name"
              value={newDepartment.name}
              onChange={(v) =>
                setNewDepartment((d) => ({
                  ...d,
                  name: v,
                }))
              }
            />

            <Input
              label="Description"
              value={newDepartment.description}
              onChange={(v) =>
                setNewDepartment((d) => ({
                  ...d,
                  description: v,
                }))
              }
            />

            <div className="mt-2">
              <Button
                onClick={async () => {
                  const departmentName = newDepartment.name.trim();

                  if (!departmentName) {
                    setError("Department name is required.");
                    return;
                  }

                  setBusy(true);
                  setError("");
                  setNotice("");

                  try {
                    await createDepartment({
                      name: departmentName,
                      description: newDepartment.description,
                    });

                    setNewDepartment({
                      name: "",
                      description: "",
                    });

                    setNotice("Department created successfully.");
                  } catch (err) {
                    setError(err.message || "Failed to create department.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !newDepartment.name.trim()}
              >
                Create Department
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">Assign User Role</div>
            <Select
              label="User"
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={userOptions}
            />
            <Select
              label="Role"
              value={selectedUserRoleId}
              onChange={setSelectedUserRoleId}
              options={roleOptions}
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  if (!selectedUserId || !selectedUserRoleId) return;
                  if (
                    !users.some(
                      (u) => String(u.user_id) === String(selectedUserId),
                    )
                  ) {
                    setError("Selected user is not in backend list.");
                    return;
                  }
                  if (
                    !roles.some(
                      (r) => String(r.id) === String(selectedUserRoleId),
                    )
                  ) {
                    setError("Selected role is not in backend list.");
                    return;
                  }
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await assignRoleToUser(
                      String(selectedUserId),
                      Number(selectedUserRoleId),
                    );
                    setNotice("Role assigned to user.");
                  } catch (err) {
                    setError(err.message || "Failed to assign role.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId || !selectedUserRoleId}
              >
                Assign Role
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Assign User Business Unit
            </div>
            <Select
              label="User"
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={userOptions}
            />
            <Select
              label="Business Unit"
              value={selectedBuId}
              onChange={setSelectedBuId}
              options={buOptions}
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  if (!selectedUserId || !selectedBuId) return;
                  if (
                    !users.some(
                      (u) => String(u.user_id) === String(selectedUserId),
                    )
                  ) {
                    setError("Selected user is not in backend list.");
                    return;
                  }
                  if (
                    !businessUnits.some(
                      (b) => String(b.id) === String(selectedBuId),
                    )
                  ) {
                    setError("Selected business unit is not in backend list.");
                    return;
                  }
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await setBusinessUnitForUser(
                      String(selectedUserId),
                      Number(selectedBuId),
                    );
                    setNotice("Business unit assigned.");
                  } catch (err) {
                    setError(err.message || "Failed to assign business unit.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId || !selectedBuId}
              >
                Set Business Unit
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Role Permission Mapping
            </div>
            <Select
              label="Role"
              value={selectedRoleId}
              onChange={setSelectedRoleId}
              options={roleOptions}
            />
            <Select
              label="Permission"
              value={selectedPermissionId}
              onChange={setSelectedPermissionId}
              options={permissionOptions}
            />
            <div className="mt-2 flex gap-2">
              <Button
                onClick={async () => {
                  if (!selectedRoleId || !selectedPermissionId) return;
                  if (
                    !roles.some((r) => String(r.id) === String(selectedRoleId))
                  ) {
                    setError("Selected role is not in backend list.");
                    return;
                  }
                  if (
                    !permissions.some(
                      (p) => String(p.id) === String(selectedPermissionId),
                    )
                  ) {
                    setError("Selected permission is not in backend list.");
                    return;
                  }
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await assignPermissionToRole(
                      Number(selectedRoleId),
                      Number(selectedPermissionId),
                    );
                    await refreshRoleDetail(selectedRoleId);
                    setNotice("Permission assigned to role.");
                  } catch (err) {
                    setError(err.message || "Failed to assign permission.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedRoleId || !selectedPermissionId}
              >
                Assign Permission
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Assign User Department
            </div>
            <Select
              label="Select User"
              value={userForDept}
              onChange={setUserForDept}
              options={userOptions}
            />
            <Select
              label="Select Department"
              value={selectedDept}
              onChange={setSelectedDept}
              options={deptOptions}
            />
            <div className="mt-2">
              <Button
                onClick={async () => {
                  if (!userForDept || !selectedDept) return;
                  if (
                    !users.some(
                      (u) => String(u.user_id) === String(userForDept),
                    )
                  ) {
                    setError("Selected user is not in backend list.");
                    return;
                  }
                  if (
                    !department.some(
                      (b) => String(b.id) === String(selectedDept),
                    )
                  ) {
                    setError("Selected Department is not in backend list.");
                    return;
                  }
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await setDepartmentForUser(
                      String(userForDept),
                      Number(selectedDept),
                    );
                    toast.success("Department assigned.");
                  } catch (err) {
                    setError(err.message || "Failed to assign business unit.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !userForDept || !selectedDept}
              >
                Set Department
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card title="Maintenance Actions">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Role Update / Delete
            </div>
            <Select
              label="Role"
              value={selectedRoleId}
              onChange={setSelectedRoleId}
              options={roleOptions}
            />
            <div className="mt-2 grid gap-2">
              <Input
                label="Name"
                value={editRole.name}
                onChange={(v) => setEditRole((r) => ({ ...r, name: v }))}
              />
              <Input
                label="Description"
                value={editRole.description}
                onChange={(v) => setEditRole((r) => ({ ...r, description: v }))}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                onClick={async () => {
                  if (!selectedRoleId) return;
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await updateRole(Number(selectedRoleId), editRole);
                    await refreshRoleDetail(selectedRoleId);
                    await loadAll();
                    setNotice("Role updated.");
                  } catch (err) {
                    setError(err.message || "Failed to update role.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedRoleId || !editRole.name.trim()}
              >
                Update Role
              </Button>
              <Button
                variant="danger"
                onClick={async () => {
                  if (!selectedRoleId) return;
                  if (!window.confirm("Delete this role?")) return;
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await deleteRole(Number(selectedRoleId));
                    await loadAll();
                    setSelectedRoleId("");
                    setRoleDetail(null);
                    setNotice("Role deleted.");
                  } catch (err) {
                    setError(err.message || "Failed to delete role.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedRoleId}
              >
                Delete Role
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-gray-50 p-4">
            <div className="mb-2 text-sm font-semibold">
              Permission / Business Unit / User
            </div>
            <Select
              label="Permission (for delete)"
              value={selectedPermissionId}
              onChange={setSelectedPermissionId}
              options={permissionOptions}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="danger"
                onClick={async () => {
                  if (!selectedPermissionId) return;
                  if (!window.confirm("Delete this permission?")) return;
                  setBusy(true);
                  setError("");
                  setNotice("");
                  try {
                    await deletePermission(Number(selectedPermissionId));
                    await loadAll();
                    setNotice("Permission deleted.");
                  } catch (err) {
                    setError(err.message || "Failed to delete permission.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedPermissionId}
              >
                Delete Permission
              </Button>
            </div>

            <div className="mt-4">
              <Select
                label="Business Unit (for update/delete)"
                value={selectedBuId}
                onChange={setSelectedBuId}
                options={buOptions}
              />
              <div className="mt-2 grid gap-2">
                <Input
                  label="BU Name"
                  value={editBu.name}
                  onChange={(v) => setEditBu((b) => ({ ...b, name: v }))}
                />
                <Input
                  label="BU Description"
                  value={editBu.description}
                  onChange={(v) => setEditBu((b) => ({ ...b, description: v }))}
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  onClick={async () => {
                    if (!selectedBuId) return;
                    setBusy(true);
                    setError("");
                    setNotice("");
                    try {
                      await updateBusinessUnit(Number(selectedBuId), editBu);
                      await loadAll();
                      setNotice("Business unit updated.");
                    } catch (err) {
                      setError(
                        err.message || "Failed to update business unit.",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                  disabled={busy || !selectedBuId || !editBu.name.trim()}
                >
                  Update BU
                </Button>
                <Button
                  variant="danger"
                  onClick={async () => {
                    if (!selectedBuId) return;
                    if (!window.confirm("Delete this business unit?")) return;
                    setBusy(true);
                    setError("");
                    setNotice("");
                    try {
                      await deleteBusinessUnit(Number(selectedBuId));
                      await loadAll();
                      setSelectedBuId("");
                      setEditBu({ name: "", description: "" });
                      setNotice("Business unit deleted.");
                    } catch (err) {
                      setError(
                        err.message || "Failed to delete business unit.",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                  disabled={busy || !selectedBuId}
                >
                  Delete BU
                </Button>
              </div>
            </div>

            <div className="mt-4">
              <Select
                label="User (for role revoke)"
                value={selectedUserId}
                onChange={setSelectedUserId}
                options={userOptions}
              />
              <div className="mt-3 flex justify-end">
                <Button
                  variant="danger"
                  onClick={async () => {
                    if (!selectedUserId) return;
                    if (!window.confirm("Revoke this user role?")) return;
                    setBusy(true);
                    setError("");
                    setNotice("");
                    try {
                      await revokeUserRole(String(selectedUserId));
                      await loadAll();
                      setNotice("User role revoked.");
                    } catch (err) {
                      setError(err.message || "Failed to revoke user role.");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  disabled={busy || !selectedUserId}
                >
                  Revoke User Role
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card title="User RBAC Details">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border bg-gray-50 p-4">
            <Select
              label="User"
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={userOptions}
            />
            <Select
              label="Update User Business Unit"
              value={userBuUpdateId}
              onChange={setUserBuUpdateId}
              options={buOptions}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={async () => {
                  if (!selectedUserId) return;
                  setBusy(true);
                  setError("");
                  setUserDetailNotice("");
                  try {
                    const summary =
                      await getUserPermissionSummary(selectedUserId);
                    setUserPermissionSummary(summary || null);
                    setUserDetailNotice("Permission summary loaded.");
                  } catch (err) {
                    setError(err.message || "Failed to load user permissions.");
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId}
              >
                Load Permission Summary
              </Button>
              <Button
                variant="secondary"
                onClick={async () => {
                  if (!selectedUserId) return;
                  setBusy(true);
                  setError("");
                  setUserDetailNotice("");
                  try {
                    const role = await getUserRole(selectedUserId);
                    setUserRoleDetail(role || null);
                    setUserDetailNotice("User role loaded.");
                  } catch (err) {
                    setUserRoleDetail(null);
                    const message = String(err.message || "");
                    if (message.toLowerCase().includes("no role assigned")) {
                      setUserDetailNotice("No role assigned to this user.");
                    } else {
                      setError(message || "Failed to load user role.");
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId}
              >
                Load User Role
              </Button>
              <Button
                variant="secondary"
                onClick={async () => {
                  if (!selectedUserId) return;
                  setBusy(true);
                  setError("");
                  setUserDetailNotice("");
                  try {
                    const bu = await getUserBusinessUnit(selectedUserId);
                    setUserBusinessUnitDetail(bu || null);
                    setUserBuUpdateId(String(bu?.id || ""));
                    setUserDetailNotice("User business unit loaded.");
                  } catch (err) {
                    setUserBusinessUnitDetail(null);
                    const message = String(err.message || "");
                    if (
                      message
                        .toLowerCase()
                        .includes("no business unit assigned")
                    ) {
                      setUserDetailNotice(
                        "No business unit assigned to this user.",
                      );
                    } else {
                      setError(message || "Failed to load user business unit.");
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId}
              >
                Load User Business Unit
              </Button>
              <Button
                onClick={async () => {
                  if (!selectedUserId || !userBuUpdateId) return;
                  setBusy(true);
                  setError("");
                  setNotice("");
                  setUserDetailNotice("");
                  try {
                    await updateUserBusinessUnit(
                      selectedUserId,
                      Number(userBuUpdateId),
                    );
                    const bu = await getUserBusinessUnit(selectedUserId);
                    setUserBusinessUnitDetail(bu || null);
                    await loadAll();
                    setNotice("User business unit updated.");
                  } catch (err) {
                    setError(
                      err.message || "Failed to update user business unit.",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
                disabled={busy || !selectedUserId || !userBuUpdateId}
              >
                Update User BU
              </Button>
            </div>
            {userDetailNotice ? (
              <div className="mt-2 text-xs text-gray-600">
                {userDetailNotice}
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border bg-white p-4 text-sm">
            <div className="mb-2 font-semibold">Loaded User Details</div>
            <div className="space-y-2 text-xs text-gray-700">
              <div>
                <span className="font-semibold">Role:</span>{" "}
                {userRoleDetail
                  ? `${userRoleDetail.name} (${userRoleDetail.id})`
                  : "-"}
              </div>
              <div>
                <span className="font-semibold">Business Unit:</span>{" "}
                {userBusinessUnitDetail
                  ? `${userBusinessUnitDetail.name} (${userBusinessUnitDetail.id})`
                  : "-"}
              </div>
              <div>
                <span className="font-semibold">Permissions:</span>{" "}
                {userPermissionSummary?.permissions?.length || 0}
              </div>
              {userPermissionSummary?.permissions?.length ? (
                <ul className="max-h-40 list-disc overflow-auto pl-5">
                  {userPermissionSummary.permissions.map((permission) => (
                    <li key={permission}>{permission}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        </div>
      </Card>

      <Card title="Role Details">
        {!selectedRoleId ? (
          <div className="text-sm text-gray-600">Select a role to inspect.</div>
        ) : roleDetail ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-xl border bg-white p-3">
              <div className="mb-2 text-sm font-semibold">Attributes</div>
              {roleDetail.attributes?.length ? (
                <div className="space-y-1">
                  {roleDetail.attributes.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>{a.attribute_name}</span>
                      <StatusBadge
                        status={a.attribute_value ? "true" : "false"}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">No attributes.</div>
              )}
            </div>

            <div className="rounded-xl border bg-white p-3">
              <div className="mb-2 text-sm font-semibold">Permissions</div>
              {roleDetail.permissions?.length ? (
                <div className="space-y-1">
                  {roleDetail.permissions.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <span>{p.name}</span>
                      <Button
                        variant="secondary"
                        onClick={async () => {
                          setBusy(true);
                          setError("");
                          setNotice("");
                          try {
                            await removePermissionFromRole(
                              Number(selectedRoleId),
                              Number(p.id),
                            );
                            await refreshRoleDetail(selectedRoleId);
                            setNotice("Permission removed.");
                          } catch (err) {
                            setError(
                              err.message || "Failed to remove permission.",
                            );
                          } finally {
                            setBusy(false);
                          }
                        }}
                        disabled={busy}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  No permissions assigned.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-600">
            Unable to load role details.
          </div>
        )}
      </Card>
    </div>
  );
}
