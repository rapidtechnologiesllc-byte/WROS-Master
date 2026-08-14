// DEFECT-2: Consolidated Employees Screen
// Consolidates EmployeeDirectoryScreen + ResourceManagementScreen + AllocationsScreen
// Tab 1: Employee List (name, email, role, hire_status, org_position, utilization %)
// Tab 2: Allocations (manage employee allocations, assign to projects)
// Tab 3: Resources (skill matrix, availability heatmap)

import { useEffect, useState } from "react";
import { Users, Briefcase, Grid3x3, UserPlus, ArrowRightLeft, RefreshCw, AlertCircle, CheckCircle2, Search } from "lucide-react";
import { Card, Button, Input, Select, TextArea, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import { getAllEmployees, createEmployee, convertCandidateToEmployee, markEmployeeOnBench, removeEmployeeFromBench } from "../services/api/employees";
import { createAllocation, getAllocations, endAllocation, getAllocationDropdowns } from "../services/api/allocations";

const EMPLOYMENT_TYPES = [
  { value: "INTERN", label: "Intern" },
  { value: "PERMANENT", label: "Full Time" },
  { value: "CONTRACT", label: "Contract" },
];

const BENCH_REASONS = [
  { value: "PROJECT_ENDED", label: "Project Ended" },
  { value: "PROJECT_DELAYED", label: "Project Delayed" },
  { value: "NEWLY_JOINED", label: "Newly Joined" },
  { value: "BETWEEN_PROJECTS", label: "Between Projects" },
  { value: "OTHER", label: "Other" },
];

function EmployeeListTab() {
  const [employees, setEmployees] = useState([]);
  const [filteredEmployees, setFilteredEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [error, setError] = useState("");

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
              <th className="px-4 py-2 text-left font-semibold">Title</th>
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
                <td className="px-4 py-2">{emp.current_title || "—"}</td>
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
          onClose={() => setSelectedEmployee(null)}
          onRefresh={loadEmployees}
        />
      )}
    </div>
  );
}

function EmployeeDetailModal({ employee, onClose, onRefresh }) {
  const [allocations, setAllocations] = useState([]);
  const [loadingAllocs, setLoadingAllocs] = useState(true);
  const [currentCert, setCurrentCert] = useState(employee.guidewire_certification_current || "None");
  const [expectedCert, setExpectedCert] = useState(employee.guidewire_certification_expected || "None");
  const [saving, setSaving] = useState(false);

  const CERT_LEVELS = ["None", "ACE", "Associate", "Specialist"];

  useEffect(() => {
    loadAllocations();
  }, [employee.id]);

  const loadAllocations = async () => {
    setLoadingAllocs(true);
    try {
      const data = await getAllocations();
      setAllocations((data || []).filter((a) => a.employee_id === employee.id));
    } catch (err) {
      console.error("Failed to load allocations:", err);
    } finally {
      setLoadingAllocs(false);
    }
  };

  const saveCertifications = async () => {
    setSaving(true);
    try {
      // TODO: Call API to save certifications
      // await updateEmployeeCertifications(employee.id, { currentCert, expectedCert });
      console.log("Saving certifications:", { currentCert, expectedCert });
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
              <Badge variant={employee.hire_status === "ACTIVE" ? "success" : "default"}>
                {employee.hire_status || "Active"}
              </Badge>
            </div>
            <div>
              <div className="font-semibold text-gray-700">Utilization</div>
              <div>{employee.utilization_pct || 0}%</div>
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
    if (!window.confirm("End this allocation?")) return;
    try {
      await endAllocation(allocationId);
      loadAllocations();
    } catch (err) {
      setError(err.message || "Failed to end allocation");
    }
  }
}

function AllocationForm({ onCancel, onSaved }) {
  const [employeeId, setEmployeeId] = useState("");
  const [demandId, setDemandId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [demands, setDemands] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getAllocationDropdowns();
        const empOptions = (data?.employees || []).map((e) => ({
          value: e.id,
          label: `${e.name} • ${e.job_title || ""}`,
        }));
        setEmployees(empOptions);
        setDemands((data?.demands || []).map((d) => ({ value: d.id, label: d.name })));
      } catch (err) {
        console.error("Failed to load dropdown data:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    if (!employeeId || !demandId) {
      setError("Employee and Demand are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createAllocation({
        employeeId,
        demandId,
        projectId: projectId || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        utilizationPct: utilizationPct ? Number(utilizationPct) : 100,
      });
      onSaved();
    } catch (err) {
      setError(err.message || "Allocation blocked.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Loading form...</div>;

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-3">Add Employee Allocation</h3>
      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Select label="Employee" value={employeeId} onChange={setEmployeeId} options={employees} />
        <Select label="Demand" value={demandId} onChange={setDemandId} options={demands} />
        <Input label="Project ID (optional)" value={projectId} onChange={setProjectId} />
        <Input label="Utilization %" type="number" value={utilizationPct} onChange={setUtilizationPct} />
        <Input label="Start Date" type="date" value={startDate} onChange={setStartDate} />
        <Input label="End Date (optional)" type="date" value={endDate} onChange={setEndDate} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSave}>
          {saving ? "Saving…" : "Create Allocation"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </Card>
  );
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

export default function EmployeesConsolidatedScreen() {
  const [activeTab, setActiveTab] = useState("list");

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
