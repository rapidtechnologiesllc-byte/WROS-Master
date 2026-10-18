// DEFECT-2: Consolidated Employees Screen
// Consolidates EmployeeDirectoryScreen + ResourceManagementScreen + AllocationsScreen
// Tab 1: Employee List (name, email, role, hire_status, org_position, utilization %)
// Tab 2: Allocations (manage employee allocations, assign to projects)
// Tab 3: Resources (skill matrix, availability heatmap)

import { useCallback, useEffect, useState } from "react";
import { Users, Briefcase, Grid3x3, UserPlus, RefreshCw, AlertCircle } from "lucide-react";
import { Card, Button, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import useTabParam from "../utils/useTabParam";
import {
  getAllEmployees,
  getEmployeeEscalations,
  raiseEmployeeEscalation,
  resolveEmployeeEscalation,
  updateEmployeeCertifications,
  updateEmployeeOrganization,
} from "../services/api/employees";
import { apiRequest } from "../services/api/client";
import { getAllocations, endAllocation } from "../services/api/allocations";
import AllocationForm from "../components/AllocationForm";
import { confirmDialog } from "../utils/dialogs";

// Our companies (Users & Access Control > Companies) and business units
const COMPANIES_PATH = "/api/v1/api/admin/users-access-control/delivery-centers";
const loadOrgOptions = () => Promise.all([apiRequest(COMPANIES_PATH), apiRequest("/rbac/business-units")])
  .then(([c, b]) => ({ companies: c.data?.delivery_centers || [], businessUnits: b.data?.business_units || [] }));

function EmployeeListTab() {
  const [employees, setEmployees] = useState([]);
  const [filteredEmployees, setFilteredEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [error, setError] = useState("");
  const [orgOptions, setOrgOptions] = useState({ companies: [], businessUnits: [] });

  useEffect(() => {
    loadOrgOptions()
      .then(setOrgOptions)
      .catch((err) => setError(`Could not load companies/business units: ${err.message}`));
  }, []);

  useEffect(() => {
    loadEmployees();
  }, []);

  useEffect(() => {
    const filtered = employees.filter((e) =>
      `${e.first_name} ${e.last_name} ${e.email}`.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredEmployees(filtered);
  }, [searchTerm, employees]);

  const loadEmployees = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAllEmployees();
      setEmployees(data || []);
    } catch (err) {
      setError(err.message || "Failed to load employees");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="py-8 text-center text-gray-500">Loading employees...</div>;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Search by name or email..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 rounded-lg border px-3 py-2 text-sm"
        />
        <Button variant="ghost" onClick={loadEmployees}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertCircle className="mb-1 inline h-4 w-4" /> {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left font-semibold">Name</th>
              <th className="px-4 py-2 text-left font-semibold">Email</th>
              <th className="px-4 py-2 text-left font-semibold">Job Title</th>
              <th className="px-4 py-2 text-left font-semibold">Company</th>
              <th className="px-4 py-2 text-left font-semibold">Business Unit</th>
              <th className="px-4 py-2 text-left font-semibold">Status</th>
              <th className="px-4 py-2 text-left font-semibold">Utilization</th>
              <th className="px-4 py-2 text-left font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredEmployees.map((emp) => (
              <tr key={emp.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2">{emp.first_name} {emp.last_name}</td>
                <td className="px-4 py-2 text-gray-600">{emp.email}</td>
                <td className="px-4 py-2">{emp.job_title || emp.current_title || "—"}</td>
                <td className="px-4 py-2">{orgOptions.companies.find((c) => c.id === emp.company_id)?.name || <span className="text-amber-700">Not set</span>}</td>
                <td className="px-4 py-2">{orgOptions.businessUnits.find((b) => b.id === emp.bu_id)?.name || "—"}</td>
                <td className="px-4 py-2">
                  <StatusBadge status={emp.hire_status === "ACTIVE" ? "active" : "inactive"}>
                    {emp.hire_status || "Active"}
                  </StatusBadge>
                </td>
                <td className="px-4 py-2">{emp.utilization_pct || 0}%</td>
                <td className="px-4 py-2">
                  <Button variant="ghost" size="sm" onClick={() => setSelectedEmployee(emp)}>
                    View
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedEmployee && (
        <EmployeeDetailModal
          employee={selectedEmployee}
          orgOptions={orgOptions}
          onClose={() => setSelectedEmployee(null)}
          onRefresh={loadEmployees}
        />
      )}
    </div>
  );
}

// Escalations (CEO 2026-10-14): an open one keeps the employee away from every client, Core and
// Staff Aug alike, until a Director or above resolves it with a note. The API decides who may
// resolve; a refusal is shown, not hidden.
function EscalationsPanel({ employeeId }) {
  const [rows, setRows] = useState([]);
  const [reason, setReason] = useState("");
  const [severity, setSeverity] = useState("MEDIUM");
  const [notes, setNotes] = useState({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getEmployeeEscalations(employeeId);
      setRows(data?.escalations || []);
    } catch (err) {
      console.error("[Escalations] Failed to load:", err);
      setMessage(`Failed to load escalations: ${err.message}`);
    }
  }, [employeeId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (action, done) => {
    setBusy(true);
    setMessage("");
    try {
      await action();
      done();
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-t pt-4">
      <h3 className="font-semibold mb-1">Escalations</h3>
      <p className="text-xs text-gray-500 mb-3">An open escalation blocks every client submission and deployment.</p>
      {message ? <div className="mb-2 text-xs text-rose-700">{message}</div> : null}
      <div className="space-y-2 mb-3">
        {rows.length === 0 ? <div className="text-sm text-gray-500">No escalations</div> : null}
        {rows.map((e) => (
          <div key={e.id} className={cx("rounded border p-2 text-sm", e.status === "OPEN" ? "bg-rose-50" : "bg-gray-50")}>
            <div className="font-semibold">
              {e.status} · {e.severity}
            </div>
            <div className="text-gray-700">{e.reason}</div>
            {e.status === "OPEN" ? (
              <div className="mt-2 flex gap-2">
                <input
                  value={notes[e.id] || ""}
                  onChange={(ev) => setNotes((prev) => ({ ...prev, [e.id]: ev.target.value }))}
                  placeholder="Resolution note (Director and above)"
                  className="flex-1 rounded border px-2 py-1 text-sm"
                />
                <Button
                  size="sm"
                  disabled={busy || !(notes[e.id] || "").trim()}
                  onClick={() => run(() => resolveEmployeeEscalation(e.id, notes[e.id].trim()),
                    () => setNotes((prev) => ({ ...prev, [e.id]: "" })))}
                >
                  Resolve
                </Button>
              </div>
            ) : (
              <div className="text-xs text-gray-500 mt-1">Resolved: {e.resolution_note}</div>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={reason}
          onChange={(ev) => setReason(ev.target.value)}
          placeholder="Reason for the escalation"
          className="flex-1 rounded border px-2 py-1 text-sm"
        />
        <select value={severity} onChange={(ev) => setSeverity(ev.target.value)} className="rounded border px-2 py-1 text-sm">
          {["LOW", "MEDIUM", "HIGH"].map((level) => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
        <Button
          size="sm"
          variant="danger"
          disabled={busy || reason.trim().length < 3}
          onClick={() => run(() => raiseEmployeeEscalation(employeeId, { reason: reason.trim(), severity }), () => setReason(""))}
        >
          Raise
        </Button>
      </div>
    </div>
  );
}

function EmployeeDetailModal({ employee, orgOptions, onClose, onRefresh }) {
  const [allocations, setAllocations] = useState([]);
  const [loadingAllocs, setLoadingAllocs] = useState(true);
  const [currentCert, setCurrentCert] = useState(employee.guidewire_certification_current || "None");
  const [expectedCert, setExpectedCert] = useState(employee.guidewire_certification_expected || "None");
  const [saving, setSaving] = useState(false);
  const [companyId, setCompanyId] = useState(employee.company_id || "");
  const [buId, setBuId] = useState(employee.bu_id ? String(employee.bu_id) : "");
  const [orgMessage, setOrgMessage] = useState("");

  const CERT_LEVELS = ["None", "ACE", "Associate", "Specialist"];

  const saveOrganization = async () => {
    setSaving(true);
    setOrgMessage("");
    try {
      await updateEmployeeOrganization(employee.id, { company_id: companyId, business_unit_id: buId ? Number(buId) : null });
      setOrgMessage("Saved");
      onRefresh();
    } catch (err) {
      console.error("[EmployeeDetailModal] Failed to save company/BU:", err);
      setOrgMessage(`Failed to save: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const loadAllocations = useCallback(async () => {
    setLoadingAllocs(true);
    try {
      const data = await getAllocations();
      setAllocations((data || []).filter((a) => a.employee_id === employee.id));
    } catch (err) {
      console.error("Failed to load allocations:", err);
    } finally {
      setLoadingAllocs(false);
    }
  }, [employee.id]);

  useEffect(() => {
    loadAllocations();
  }, [loadAllocations]);

  const saveCertifications = async () => {
    setSaving(true);
    try {
      await updateEmployeeCertifications(employee.id, {
        guidewire_certification_current: currentCert,
        guidewire_certification_expected: expectedCert,
      });
      onRefresh();
    } catch (err) {
      console.error("Failed to save certifications:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <Card className="w-full max-w-2xl max-h-96 overflow-y-auto">
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-lg font-semibold">
            {employee.first_name} {employee.last_name}
          </h2>
          <Button variant="ghost" onClick={onClose}>
            ✕
          </Button>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="font-semibold text-gray-700">Email</div>
              <div>{employee.email}</div>
            </div>
            <div>
              <div className="font-semibold text-gray-700">Title</div>
              <div>{employee.current_title || "—"}</div>
            </div>
            <div>
              <div className="font-semibold text-gray-700">Status</div>
              <StatusBadge status={employee.hire_status === "ACTIVE" ? "active" : "inactive"}>
                {employee.hire_status || "Active"}
              </StatusBadge>
            </div>
            <div>
              <div className="font-semibold text-gray-700">Utilization</div>
              <div>{employee.utilization_pct || 0}%</div>
            </div>
          </div>

          <div className="border-t pt-4">
            <h3 className="font-semibold mb-1">Company &amp; Business Unit</h3>
            <p className="text-xs text-gray-500 mb-3">Headcount is counted by employer company and business unit.</p>
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Company (employer)</label>
                <select value={companyId} onChange={(e) => setCompanyId(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="">Not set</option>
                  {orgOptions.companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Business Unit</label>
                <select value={buId} onChange={(e) => setBuId(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
                  <option value="">Not set</option>
                  {orgOptions.businessUnits.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <Button variant="primary" size="sm" onClick={saveOrganization} disabled={saving}>
                {saving ? "Saving..." : "Save Company & BU"}
              </Button>
              {orgMessage && <span className="text-xs text-gray-600">{orgMessage}</span>}
            </div>
          </div>

          <div className="border-t pt-4">
            <h3 className="font-semibold mb-3">Guidewire Certification</h3>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Current Level</label>
                <select
                  value={currentCert}
                  onChange={(e) => setCurrentCert(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                >
                  {CERT_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Expected Level</label>
                <select
                  value={expectedCert}
                  onChange={(e) => setExpectedCert(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                >
                  {CERT_LEVELS.map((level) => (
                    <option key={level} value={level}>{level}</option>
                  ))}
                </select>
              </div>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={saveCertifications}
              disabled={saving}
              className="mb-4"
            >
              {saving ? "Saving..." : "Save Certification"}
            </Button>
          </div>

          <EscalationsPanel employeeId={employee.id} />

          <div className="border-t pt-4">
            <h3 className="font-semibold mb-3">Current Allocations</h3>
            {loadingAllocs ? (
              <div className="text-gray-500 text-sm">Loading allocations...</div>
            ) : allocations.length === 0 ? (
              <div className="text-gray-500 text-sm">No active allocations</div>
            ) : (
              <div className="space-y-2">
                {allocations.map((alloc) => (
                  <div key={alloc.id} className="rounded border p-2 bg-gray-50 text-sm">
                    <div className="font-semibold">{alloc.project_name || "Project"}</div>
                    <div className="text-gray-600">{alloc.utilization_pct}% allocation</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="border-t p-4 flex gap-2">
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
    </div>
  );
}

function AllocationsTab() {
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAllocations();
  }, []);

  const loadAllocations = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAllocations();
      setAllocations(data || []);
    } catch (err) {
      setError(err.message || "Failed to load allocations");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="py-8 text-center text-gray-500">Loading allocations...</div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Button variant="primary" onClick={() => setShowForm(true)}>
          <UserPlus className="h-4 w-4" /> Add Allocation
        </Button>
        <Button variant="ghost" onClick={loadAllocations}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertCircle className="mb-1 inline h-4 w-4" /> {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left font-semibold">Employee</th>
              <th className="px-4 py-2 text-left font-semibold">Project</th>
              <th className="px-4 py-2 text-left font-semibold">Allocation %</th>
              <th className="px-4 py-2 text-left font-semibold">Start Date</th>
              <th className="px-4 py-2 text-left font-semibold">End Date</th>
              <th className="px-4 py-2 text-left font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {allocations.map((alloc) => (
              <tr key={alloc.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2">{alloc.employee_name || "—"}</td>
                <td className="px-4 py-2">{alloc.project_name || "—"}</td>
                <td className="px-4 py-2">{alloc.utilization_pct}%</td>
                <td className="px-4 py-2 text-gray-600">{alloc.start_date || "—"}</td>
                <td className="px-4 py-2 text-gray-600">{alloc.end_date || "Ongoing"}</td>
                <td className="px-4 py-2">
                  <Button variant="ghost" size="sm" onClick={() => handleEndAllocation(alloc.id)}>
                    End
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <AllocationForm
          onCancel={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadAllocations(); }}
        />
      )}
    </div>
  );

  async function handleEndAllocation(allocationId) {
    if (!(await confirmDialog("End this allocation?"))) return;
    try {
      await endAllocation(allocationId);
      loadAllocations();
    } catch (err) {
      setError(err.message || "Failed to end allocation");
    }
  }
}

function ResourcesTab() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    setLoading(true);
    try {
      const data = await getAllEmployees();
      setEmployees(data || []);
    } catch (err) {
      console.error("Failed to load employees:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="py-8 text-center text-gray-500">Loading resources...</div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-lg">Resource Availability</h3>
        <Button variant="ghost" onClick={loadEmployees}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <div className="p-4">
          <h4 className="font-semibold mb-3">Team Utilization Heatmap</h4>
          <div className="space-y-2">
            {employees.map((emp) => {
              const utilization = emp.utilization_pct || 0;
              const bgColor =
                utilization >= 100 ? "bg-red-100" :
                utilization >= 75 ? "bg-yellow-100" :
                utilization >= 50 ? "bg-green-100" :
                "bg-blue-100";
              return (
                <div key={emp.id} className="flex items-center gap-3">
                  <div className="w-24 text-sm font-medium truncate">
                    {emp.first_name} {emp.last_name}
                  </div>
                  <div className={`flex-1 h-6 rounded ${bgColor} flex items-center justify-center text-xs font-semibold`}>
                    {utilization}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-4">
          <h4 className="font-semibold mb-3">Skills Inventory</h4>
          <div className="text-sm text-gray-600">
            <div className="mb-2">Total Employees: {employees.length}</div>
            <div>Active Employees: {employees.filter((e) => e.hire_status === "ACTIVE").length}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

const EMPLOYEE_TABS = ["list", "allocations", "resources"];

export default function EmployeesConsolidatedScreen() {
  // ?tab=allocations is where the retired /allocations menu item lands
  const [activeTab, setActiveTab] = useTabParam(EMPLOYEE_TABS);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Employees</h1>
        <p className="text-gray-600">Manage employee profiles, allocations, and resources</p>
      </div>

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("list")}
          className={cx(
            "px-4 py-2 font-medium border-b-2",
            activeTab === "list"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          )}
        >
          <Users className="inline h-4 w-4 mr-2" />
          Employee List
        </button>
        <button
          onClick={() => setActiveTab("allocations")}
          className={cx(
            "px-4 py-2 font-medium border-b-2",
            activeTab === "allocations"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          )}
        >
          <Briefcase className="inline h-4 w-4 mr-2" />
          Allocations
        </button>
        <button
          onClick={() => setActiveTab("resources")}
          className={cx(
            "px-4 py-2 font-medium border-b-2",
            activeTab === "resources"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          )}
        >
          <Grid3x3 className="inline h-4 w-4 mr-2" />
          Resources
        </button>
      </div>

      <div>
        {activeTab === "list" && <EmployeeListTab />}
        {activeTab === "allocations" && <AllocationsTab />}
        {activeTab === "resources" && <ResourcesTab />}
      </div>
    </div>
  );
}
