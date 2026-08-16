/**
 * RBAC & User Access Management Screen
 *
 * Three-panel layout:
 * - Left: Module list with search (300px)
 * - Center: Permission grid (flex) - roles × modules × verbs
 * - Right: User access manager (300px) - assign roles, copy templates, custom permissions
 */

import React, { useEffect, useState, useMemo } from "react";
import { Search, Copy, Settings, AlertCircle, CheckCircle } from "lucide-react";
import { Card, Button, Input, Select, Badge } from "../components/ui";
import {
  getModulesAndVerbs,
  getRolesMatrix,
  grantPermission,
  revokePermission,
  assignRoleToUser,
} from "../services/api/rbac";
import { getAllUsers } from "../services/api/users";
import { toast } from "react-toastify";

export default function RbacSettingsScreen() {
  // =========================================================================
  // State
  // =========================================================================

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [moduleSearch, setModuleSearch] = useState("");
  const [activeTab, setActiveTab] = useState("assign"); // assign | copy | custom

  // Data
  const [modules, setModules] = useState([]);
  const [verbMatrix, setVerbMatrix] = useState({});
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedModule, setSelectedModule] = useState(null);

  // UI selections
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [sourceRoleId, setSourceRoleId] = useState(""); // For copy template

  // Toggle states for permission grid
  const [toggleStates, setToggleStates] = useState({}); // {roleId_module_verb: boolean}
  const [toggling, setToggling] = useState({}); // {roleId_module_verb: "loading"}

  // =========================================================================
  // Load Data
  // =========================================================================

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");

      // Fetch modules and verb matrix
      const matrixRes = await getModulesAndVerbs();
      setModules(matrixRes.modules || []);
      setVerbMatrix(matrixRes.verb_matrix || {});

      // Fetch roles matrix
      const rolesRes = await getRolesMatrix();
      const rolesData = rolesRes.roles || [];
      setRoles(rolesData);

      // Initialize toggle states from roles matrix
      const initialToggles = {};
      rolesData.forEach((role) => {
        Object.entries(role.permissions).forEach(([module, verbs]) => {
          Object.entries(verbs).forEach(([verb, hasPermission]) => {
            initialToggles[`${role.id}_${module}_${verb}`] = hasPermission;
          });
        });
      });
      setToggleStates(initialToggles);

      // Fetch users
      const usersData = await getAllUsers();
      setUsers(usersData.data || usersData || []);

      setSelectedModule(matrixRes.modules?.[0] || null);
    } catch (err) {
      console.error("Failed to load RBAC data:", err);
      setError("Failed to load RBAC configuration. Please try again.");
      toast.error("Failed to load RBAC data");
    } finally {
      setLoading(false);
    }
  };

  // =========================================================================
  // Permission Toggle Handler
  // =========================================================================

  const handlePermissionToggle = async (roleId, module, verb) => {
    const key = `${roleId}_${module}_${verb}`;
    const permissionName = `${module}.${verb}`;
    const currentState = toggleStates[key];

    // Optimistic update
    setToggleStates((prev) => ({ ...prev, [key]: !currentState }));
    setToggling((prev) => ({ ...prev, [key]: "loading" }));

    try {
      if (currentState) {
        // Revoke permission
        await revokePermission(roleId, permissionName);
        toast.success(`Revoked ${permissionName} from role`);
      } else {
        // Grant permission
        await grantPermission(roleId, permissionName);
        toast.success(`Granted ${permissionName} to role`);
      }
    } catch (err) {
      console.error("Failed to toggle permission:", err);
      // Revert optimistic update
      setToggleStates((prev) => ({ ...prev, [key]: currentState }));
      toast.error(`Failed to update permission`);
    } finally {
      setToggling((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  // =========================================================================
  // User Role Assignment
  // =========================================================================

  const handleAssignRole = async () => {
    if (!selectedUserId || !selectedRoleId) {
      toast.warning("Please select a user and role");
      return;
    }

    try {
      await assignRoleToUser(selectedUserId, parseInt(selectedRoleId));
      toast.success("Role assigned successfully");
      setSelectedUserId("");
      setSelectedRoleId("");
    } catch (err) {
      console.error("Failed to assign role:", err);
      toast.error("Failed to assign role");
    }
  };

  // =========================================================================
  // Role Copy Template
  // =========================================================================

  const handleCopyRoleTemplate = async () => {
    if (!selectedUserId || !sourceRoleId) {
      toast.warning("Please select a user and source role");
      return;
    }

    try {
      // Copy all permissions from source role to target user
      const sourceRole = roles.find((r) => r.id === parseInt(sourceRoleId));
      if (!sourceRole) {
        toast.error("Source role not found");
        return;
      }

      // First assign the role
      await assignRoleToUser(selectedUserId, parseInt(sourceRoleId));

      toast.success("Role template copied to user");
      setSelectedUserId("");
      setSourceRoleId("");
    } catch (err) {
      console.error("Failed to copy role template:", err);
      toast.error("Failed to copy role template");
    }
  };

  // =========================================================================
  // Derived State
  // =========================================================================

  const categoryGroups = useMemo(() => {
    const groups = {
      Recruitment: [
        "candidates",
        "jobs",
        "interviews",
        "offers",
        "submissions",
        "offer_readiness",
        "candidate_review",
        "bulk_launch",
        "thunder_analytics",
      ],
      Sales: [
        "clients",
        "demand",
        "opportunities",
        "opportunity_pipeline",
        "partner_roi",
      ],
      ProjectManagement: [
        "employees",
        "projects",
        "allocations",
        "resource_management",
        "core_pull",
        "utilization",
        "forecast",
        "buddy_program",
        "htd_intake",
      ],
      Finance: [
        "invoices",
        "timesheets",
        "expenses",
        "revenue",
        "forecasting",
        "finance_operations",
      ],
      Admin: [
        "rbac",
        "users",
        "tenant_config",
        "locale",
        "ai_config",
        "message_templates",
        "ticket_routing",
        "documents",
        "reports",
        "tasks",
        "notifications",
        "error_log",
        "admin_settings",
        "executive_signal",
      ],
    };
    return groups;
  }, []);

  const filteredModules = useMemo(() => {
    const search = moduleSearch.toLowerCase();
    return modules.filter((m) => m.toLowerCase().includes(search));
  }, [modules, moduleSearch]);

  const userOptions = useMemo(() => {
    return users.map((u) => ({
      value: u.user_id || u.UserID,
      label: `${u.user_name || u.UserName || ""} (${u.user_email || u.UserEmail || ""})`,
    }));
  }, [users]);

  const roleOptions = useMemo(() => {
    return roles.map((r) => ({
      value: r.id,
      label: r.name,
    }));
  }, [roles]);

  // =========================================================================
  // Render
  // =========================================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-500">Loading RBAC configuration...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">
          RBAC & User Access Management
        </h1>
        <p className="text-gray-600 mt-1">
          Manage role permissions and user assignments across 45+ modules
        </p>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Main Content - Three Panel Layout */}
      <div className="flex flex-1 gap-4 p-4 overflow-hidden">
        {/* LEFT PANEL - Module List */}
        <div className="w-72 bg-white rounded-lg border border-gray-200 flex flex-col overflow-hidden shadow-sm">
          <div className="p-4 border-b border-gray-200">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search modules..."
                value={moduleSearch}
                onChange={(e) => setModuleSearch(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* Module Categories */}
          <div className="flex-1 overflow-y-auto">
            {Object.entries(categoryGroups).map(([category, categoryModules]) => {
              const visibleInCategory = categoryModules.filter((m) =>
                filteredModules.includes(m)
              );

              if (visibleInCategory.length === 0 && moduleSearch) return null;

              return (
                <div key={category} className="border-b border-gray-100 last:border-b-0">
                  <div className="px-4 py-2 bg-gray-50 font-semibold text-xs text-gray-700 uppercase tracking-wider">
                    {category}
                  </div>
                  <div className="divide-y divide-gray-100">
                    {(visibleInCategory.length > 0 ? visibleInCategory : categoryModules).map((module) => (
                      <button
                        key={module}
                        onClick={() => setSelectedModule(module)}
                        className={`w-full text-left px-4 py-2.5 text-sm font-medium transition-colors ${
                          selectedModule === module
                            ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                            : "text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        {module.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CENTER PANEL - Permission Grid */}
        <div className="flex-1 bg-white rounded-lg border border-gray-200 flex flex-col overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Permission Grid
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Click toggles to grant or revoke permissions. Roles are rows, modules/verbs are columns.
            </p>
          </div>

          {/* Scrollable Grid */}
          <div className="flex-1 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700 w-32 sticky left-0 bg-gray-50 z-10">
                    Role
                  </th>
                  {selectedModule &&
                    verbMatrix[selectedModule]?.map((verb) => (
                      <th
                        key={`${selectedModule}_${verb}`}
                        className="px-3 py-2 text-center font-semibold text-gray-700 bg-gray-50 whitespace-nowrap"
                      >
                        {verb}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {roles.map((role) => (
                  <tr key={role.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900 sticky left-0 bg-white z-10 border-r border-gray-200">
                      {role.name}
                    </td>
                    {selectedModule &&
                      verbMatrix[selectedModule]?.map((verb) => {
                        const key = `${role.id}_${selectedModule}_${verb}`;
                        const hasPermission = toggleStates[key];
                        const isLoading = toggling[key];

                        return (
                          <td
                            key={key}
                            className="px-3 py-3 text-center border-r border-gray-100"
                          >
                            <button
                              onClick={() =>
                                handlePermissionToggle(
                                  role.id,
                                  selectedModule,
                                  verb
                                )
                              }
                              disabled={isLoading}
                              className={`inline-flex items-center justify-center w-6 h-6 rounded border transition-all ${
                                hasPermission
                                  ? "bg-blue-100 border-blue-300 text-blue-700 hover:bg-blue-200"
                                  : "bg-gray-100 border-gray-300 text-gray-400 hover:bg-gray-200"
                              } ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
                            >
                              {hasPermission && (
                                <CheckCircle className="w-4 h-4" />
                              )}
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

        {/* RIGHT PANEL - User Access Manager */}
        <div className="w-80 bg-white rounded-lg border border-gray-200 flex flex-col overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              User Access Manager
            </h2>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            {[
              { id: "assign", label: "Assign Role" },
              { id: "copy", label: "Copy Template" },
              { id: "custom", label: "Custom" },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === t.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {/* Tab: Assign Role */}
            {activeTab === "assign" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    User
                  </label>
                  <Select
                    options={[
                      { value: "", label: "Select a user..." },
                      ...userOptions,
                    ]}
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Role
                  </label>
                  <Select
                    options={[
                      { value: "", label: "Select a role..." },
                      ...roleOptions,
                    ]}
                    value={selectedRoleId}
                    onChange={(e) => setSelectedRoleId(e.target.value)}
                    className="w-full"
                  />
                </div>

                <Button
                  onClick={handleAssignRole}
                  className="w-full"
                  variant="primary"
                >
                  Assign Role
                </Button>
              </div>
            )}

            {/* Tab: Copy Template */}
            {activeTab === "copy" && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    User
                  </label>
                  <Select
                    options={[
                      { value: "", label: "Select a user..." },
                      ...userOptions,
                    ]}
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Source Role (Template)
                  </label>
                  <Select
                    options={[
                      { value: "", label: "Select a role..." },
                      ...roleOptions,
                    ]}
                    value={sourceRoleId}
                    onChange={(e) => setSourceRoleId(e.target.value)}
                    className="w-full"
                  />
                </div>

                <Button
                  onClick={handleCopyRoleTemplate}
                  className="w-full"
                  variant="secondary"
                >
                  <Copy className="w-4 h-4 mr-2" />
                  Copy Template
                </Button>
              </div>
            )}

            {/* Tab: Custom */}
            {activeTab === "custom" && (
              <div className="space-y-4 text-center py-8 text-gray-500">
                <Settings className="w-12 h-12 mx-auto opacity-50" />
                <div>
                  <p className="text-sm font-medium">Custom permissions</p>
                  <p className="text-xs mt-1">
                    Fine-grained permission assignment coming soon
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
