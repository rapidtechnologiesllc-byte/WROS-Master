// DEFECT-2: Consolidated Employees Screen
// Consolidates EmployeeDirectoryScreen + ResourceManagementScreen + AllocationsScreen
// Employee List: current employees (headcount, employment + deployment, filters/sort in the URL), Import + Add
// Past Employees: terminated people, never in the headcount
// Allocations: manage employee allocations, assign to projects
// Resources: availability heatmap of current employees

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Users, UserX, Briefcase, Grid3x3, UserPlus, RefreshCw, AlertCircle, Upload } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";
import useTabParam from "../utils/useTabParam";
import {
  getAllEmployees,
  getEmployeeEscalations,
  raiseEmployeeEscalation,
  resolveEmployeeEscalation,
  updateEmployeeBillable,
  updateEmployeeOrganization,
} from "../services/api/employees";
import EmployeeCertifications from "../components/EmployeeCertifications";
import { apiRequest } from "../services/api/client";
import { getAllocations, endAllocation } from "../services/api/allocations";
import AllocationForm from "../components/AllocationForm";
import AllocationEditModal from "../components/AllocationEditModal";
import { marginLabel } from "../components/AllocationMargin";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { AddEmployeeModal, ImportEmployeesModal } from "../components/EmployeeImport";
import { EmployeeDetailsForm, EmploymentActions, HtdControl } from "../components/EmployeeEditPanels";
import { confirmDialog } from "../utils/dialogs";

// Our companies (Users & Access Control > Companies) and business units
const COMPANIES_PATH = "/api/v1/api/admin/users-access-control/delivery-centers";
const loadOrgOptions = () => Promise.all([apiRequest(COMPANIES_PATH), apiRequest("/rbac/business-units")])
  .then(([c, b]) => ({ companies: c.data?.delivery_centers || [], businessUnits: b.data?.business_units || [] }));

const statusLabel = (status) => (status || "").replace(/_/g, " ").toLowerCase();

// Where the employee stands, on two axes the server derives (app/services/employee_standing.py):
// employment, and for people on the payroll the deployment.
const TONE = {
  green: "border-green-200 bg-green-50 text-green-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  blue: "border-blue-200 bg-blue-50 text-blue-800",
  purple: "border-purple-200 bg-purple-50 text-purple-800",
  grey: "border-gray-200 bg-gray-100 text-gray-600",
};
const EMPLOYMENT = {
  JOINING: ["Joining", "blue"],
  EMPLOYED: ["Employed", "green"],
  ON_LEAVE: ["On leave", "blue"],
  SERVING_NOTICE: ["Serving notice", "amber"],
  TERMINATED: ["Terminated", "grey"],
};
const DEPLOYMENT = {
  HTD: ["HTD", "blue"],
  BUDDY: ["Buddy Program", "purple"],
  BENCH: ["Bench", "amber"],
  PROJECT: ["On project", "green"],
  PROJECT_ENDING: ["Project ending", "amber"],
};
const Pill = ({ tone, children }) => <span className={cx(pill, "whitespace-nowrap", TONE[tone])}>{children}</span>;

function EmploymentStatus({ employee }) {
  const [label, tone] = EMPLOYMENT[employee.employment_status] || [statusLabel(employee.employment_status), "grey"];
  return <Pill tone={tone}>{label}</Pill>;
}

function DeploymentStatus({ employee }) {
  const status = employee.deployment_status;
  if (!status) return <span className="text-gray-400">—</span>;
  const [label, tone] = DEPLOYMENT[status] || [statusLabel(status), "grey"];
  let detail = null;
  if (status === "BENCH" && employee.deployment_days != null) detail = `${employee.deployment_days}d on bench`;
  if (status === "PROJECT_ENDING") detail = `ends ${employee.deployment_until} (${employee.deployment_days}d)`;
  if (status === "PROJECT" && employee.deployment_until) detail = `until ${employee.deployment_until}`;
  return (
    <div>
      <Pill tone={tone}>{label}</Pill>
      {detail ? <div className="mt-0.5 whitespace-nowrap text-xs text-gray-500">{detail}</div> : null}
    </div>
  );
}

// An allocation's state: the record's status, sharpened for active ones by the ending window and
// the renewal decision.
const RENEWAL_LABEL = { IN_DISCUSSION: "renewal in discussion", EXTENDED: "extension agreed", ROLLING_OFF: "rolling off" };
function AllocationState({ alloc }) {
  let label = statusLabel(alloc.status);
  let tone = ALLOCATION_STATUS_TONE[alloc.status] || "bg-gray-100 text-gray-700";
  if (alloc.status === "ACTIVE" && alloc.ending_soon) {
    label = alloc.days_left < 0 ? `past end ${-alloc.days_left}d` : `ending in ${alloc.days_left}d`;
    tone = "bg-amber-100 text-amber-800";
  }
  return (
    <div>
      <span className={cx("whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold", tone)}>{label}</span>
      {alloc.status === "ACTIVE" && RENEWAL_LABEL[alloc.renewal_status] && (
        <div className="mt-1 whitespace-nowrap text-xs text-gray-500">{RENEWAL_LABEL[alloc.renewal_status]}</div>
      )}
    </div>
  );
}

// Filters, sort and search live in the URL (?q=&employment=&deployment=&company=&bu=&billable=&sort=&dir=)
// so a refresh, a bookmark or a shared link shows the same list.
function useUrlParam(key) {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = searchParams.get(key) || "";
  const setValue = useCallback(
    (next) => {
      setSearchParams((current) => {
        const params = new URLSearchParams(current);
        if (next) params.set(key, next);
        else params.delete(key);
        return params;
      }, { replace: true });
    },
    [key, setSearchParams],
  );
  return [value, setValue];
}

const isPast = (emp) => emp.employment_status === "TERMINATED";
const ON_PAYROLL = new Set(["EMPLOYED", "ON_LEAVE", "SERVING_NOTICE"]);
const fullName = (emp) => `${emp.first_name} ${emp.last_name}`.trim();

// Sort keys -> the value compared (strings case-insensitively, numbers numerically)
const SORTERS = {
  name: (e) => fullName(e).toLowerCase(),
  company: (e, org) => (org.companyName(e.company_id) || "").toLowerCase(),
  bu: (e, org) => (org.buName(e.bu_id) || "").toLowerCase(),
  employment: (e) => (EMPLOYMENT[e.employment_status] || [e.employment_status || ""])[0],
  deployment: (e) => (DEPLOYMENT[e.deployment_status] || [e.deployment_status || ""])[0],
  allocated: (e) => e.allocated_pct || 0,
  joined: (e) => e.joining_date || "",
  exited: (e) => e.exit_date || "",
};

function SortHeader({ label, sortKey, sort, dir, onSort }) {
  const active = sort === sortKey;
  return (
    <th className="px-4 py-2 text-left font-semibold"
      aria-sort={active ? (dir === "desc" ? "descending" : "ascending") : "none"}>
      <button type="button" onClick={() => onSort(sortKey)} className="inline-flex items-center gap-1 hover:text-gray-900">
        {label}
        <span className={cx("text-xs", active ? "text-gray-900" : "text-gray-300")}>
          {active && dir === "desc" ? "▼" : "▲"}
        </span>
      </button>
    </th>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-1 text-xs text-gray-600">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border bg-white px-2 py-1.5 text-sm text-gray-900">
        <option value="">All</option>
        {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
      </select>
    </label>
  );
}

function EmployeeListTab({ past = false }) {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [error, setError] = useState("");
  const [orgOptions, setOrgOptions] = useState({ companies: [], businessUnits: [] });
  const [dialog, setDialog] = useState(null); // "import" | "add"
  const [searchParams] = useSearchParams();
  const linkedEmployeeId = searchParams.get("employee");
  const [q, setQ] = useUrlParam("q");
  const [employment, setEmployment] = useUrlParam("employment");
  const [deployment, setDeployment] = useUrlParam("deployment");
  const [company, setCompany] = useUrlParam("company");
  const [bu, setBu] = useUrlParam("bu");
  const [billable, setBillable] = useUrlParam("billable");
  const [sortParam, setSort] = useUrlParam("sort");
  const [dir, setDir] = useUrlParam("dir");
  const sort = sortParam || (past ? "exited" : "name");

  useEffect(() => {
    loadOrgOptions()
      .then(setOrgOptions)
      .catch((err) => setError(`Could not load companies/business units: ${err.message}`));
  }, []);

  const loadEmployees = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  // The open drawer shows the reloaded record, not the copy it was opened with
  useEffect(() => {
    setSelectedEmployee((open) => (open ? employees.find((e) => e.id === open.id) || open : open));
  }, [employees]);

  // /employees?employee=<id> (the import results link) opens that employee
  useEffect(() => {
    if (!linkedEmployeeId || !employees.length) return;
    const linked = employees.find((e) => e.id === linkedEmployeeId);
    if (linked) setSelectedEmployee(linked);
  }, [linkedEmployeeId, employees]);

  const org = useMemo(() => ({
    companyName: (id) => orgOptions.companies.find((c) => c.id === id)?.name,
    buName: (id) => orgOptions.businessUnits.find((b) => b.id === id)?.name,
  }), [orgOptions]);

  // Terminated people are past employees: never in the current list or its counts
  const population = useMemo(() => employees.filter((e) => isPast(e) === past), [employees, past]);

  const counts = useMemo(() => {
    const out = { headcount: 0, joining: 0, BENCH: 0, PROJECT: 0, PROJECT_ENDING: 0, HTD: 0, BUDDY: 0 };
    population.forEach((e) => {
      if (ON_PAYROLL.has(e.employment_status)) out.headcount += 1;
      if (e.employment_status === "JOINING") out.joining += 1;
      if (e.deployment_status in out) out[e.deployment_status] += 1;
    });
    return out;
  }, [population]);

  const rows = useMemo(() => {
    const needle = q.toLowerCase();
    const filtered = population.filter((e) =>
      (!needle || `${fullName(e)} ${e.email} ${e.current_title || ""}`.toLowerCase().includes(needle))
      && (!employment || e.employment_status === employment)
      && (!deployment || e.deployment_status === deployment)
      && (!company || e.company_id === company)
      && (!bu || String(e.bu_id) === bu)
      && (!billable || (billable === "billable") === Boolean(e.is_billable)));
    const key = SORTERS[sort] || SORTERS.name;
    const sign = dir === "desc" ? -1 : 1;
    return [...filtered].sort((a, b) => {
      const x = key(a, org);
      const y = key(b, org);
      if (x < y) return -sign;
      if (x > y) return sign;
      return SORTERS.name(a).localeCompare(SORTERS.name(b));
    });
  }, [population, q, employment, deployment, company, bu, billable, sort, dir, org]);

  const onSort = (key) => {
    if (sort === key) setDir(dir === "desc" ? "" : "desc");
    else {
      setSort(key);
      setDir("");
    }
  };
  const filtersOn = q || employment || deployment || company || bu || billable;
  const clearFilters = () => [setQ, setEmployment, setDeployment, setCompany, setBu, setBillable].forEach((set) => set(""));

  if (loading) return <div className="py-8 text-center text-gray-500">Loading employees...</div>;

  const employmentOptions = Object.entries(EMPLOYMENT)
    .filter(([key]) => (key === "TERMINATED") === past)
    .map(([key, [text]]) => [key, text]);
  const chips = past ? [] : [
    ["BENCH", counts.BENCH], ["PROJECT", counts.PROJECT], ["PROJECT_ENDING", counts.PROJECT_ENDING], ["HTD", counts.HTD],
    ["BUDDY", counts.BUDDY],
  ];

  return (
    <div className="space-y-4">
      {!past && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold text-gray-900">Headcount {counts.headcount}</span>
          {counts.joining ? <span className="text-gray-500">+ {counts.joining} joining</span> : null}
          <span className="text-gray-300">|</span>
          {chips.map(([key, n]) => {
            const [label, tone] = DEPLOYMENT[key];
            return (
              <button key={key} type="button" onClick={() => setDeployment(deployment === key ? "" : key)}
                className={cx(pill, "cursor-pointer", TONE[tone], deployment === key && "ring-2 ring-offset-1 ring-gray-400")}>
                {label} {n}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search name, email or title..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="min-w-[220px] flex-1 rounded-lg border px-3 py-2 text-sm"
        />
        <Button variant="ghost" onClick={loadEmployees} title="Reload">
          <RefreshCw className="h-4 w-4" />
        </Button>
        {!past && (
          <>
            <Button variant="secondary" onClick={() => setDialog("import")}>
              <Upload className="h-4 w-4" /> Import employees
            </Button>
            <Button variant="primary" onClick={() => setDialog("add")}>
              <UserPlus className="h-4 w-4" /> Add employee
            </Button>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {employmentOptions.length > 1 && (
          <FilterSelect label="Employment" value={employment} onChange={setEmployment} options={employmentOptions} />
        )}
        {!past && (
          <FilterSelect label="Deployment" value={deployment} onChange={setDeployment}
            options={Object.entries(DEPLOYMENT).map(([key, [text]]) => [key, text])} />
        )}
        <FilterSelect label="Company" value={company} onChange={setCompany}
          options={orgOptions.companies.map((c) => [c.id, c.name])} />
        <FilterSelect label="Business unit" value={bu} onChange={setBu}
          options={orgOptions.businessUnits.map((b) => [String(b.id), b.name])} />
        {!past && (
          <FilterSelect label="Billing" value={billable} onChange={setBillable}
            options={[["billable", "Billable"], ["internal", "Internal"]]} />
        )}
        <span className="text-xs text-gray-500">
          {rows.length} of {population.length} {past ? "past employees" : "employees"}
        </span>
        {filtersOn ? (
          <button type="button" onClick={clearFilters} className="text-xs font-semibold text-blue-700 hover:underline">
            Clear filters
          </button>
        ) : null}
      </div>

      {dialog === "import" ? <ImportEmployeesModal onClose={() => setDialog(null)} onImported={loadEmployees} /> : null}
      {dialog === "add" ? (
        <AddEmployeeModal orgOptions={orgOptions} onClose={() => setDialog(null)}
          onCreated={() => { setDialog(null); loadEmployees(); }} />
      ) : null}

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          <AlertCircle className="mb-1 inline h-4 w-4" /> {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <SortHeader label="Name" sortKey="name" sort={sort} dir={dir} onSort={onSort} />
              <th className="px-4 py-2 text-left font-semibold">Job Title</th>
              <SortHeader label="Company" sortKey="company" sort={sort} dir={dir} onSort={onSort} />
              <SortHeader label="Business Unit" sortKey="bu" sort={sort} dir={dir} onSort={onSort} />
              {past ? (
                <>
                  <SortHeader label="Joined" sortKey="joined" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Exited" sortKey="exited" sort={sort} dir={dir} onSort={onSort} />
                </>
              ) : (
                <>
                  <SortHeader label="Employment" sortKey="employment" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Deployment" sortKey="deployment" sort={sort} dir={dir} onSort={onSort} />
                  <th className="px-4 py-2 text-left font-semibold">Billable</th>
                  <SortHeader label="Allocated" sortKey="allocated" sort={sort} dir={dir} onSort={onSort} />
                </>
              )}
              <th className="px-4 py-2 text-left font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((emp) => (
              <tr key={emp.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2">
                  <div className="font-medium text-gray-900">{fullName(emp)}</div>
                  <div className="text-xs text-gray-500">{emp.email}</div>
                </td>
                <td className="px-4 py-2">{emp.current_title || "—"}</td>
                <td className="px-4 py-2">{org.companyName(emp.company_id) || <span className="text-amber-700">Not set</span>}</td>
                <td className="px-4 py-2">{org.buName(emp.bu_id) || "—"}</td>
                {past ? (
                  <>
                    <td className="px-4 py-2 whitespace-nowrap">{emp.joining_date || "—"}</td>
                    <td className="px-4 py-2 whitespace-nowrap">{emp.exit_date || "—"}</td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2">
                      <EmploymentStatus employee={emp} />
                      {!emp.has_login ? <div className="text-xs text-amber-700">no login</div> : null}
                    </td>
                    <td className="px-4 py-2"><DeploymentStatus employee={emp} /></td>
                    <td className="px-4 py-2">{emp.is_billable ? "Billable" : "Internal"}</td>
                    <td className="px-4 py-2">{emp.allocated_pct}%</td>
                  </>
                )}
                <td className="px-4 py-2">
                  <Button variant="ghost" size="sm" onClick={() => setSelectedEmployee(emp)}>
                    View
                  </Button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={past ? 7 : 9} className="px-4 py-8 text-center text-gray-500">
                  {population.length ? "No one matches these filters." : past ? "No past employees." : "No employees yet."}
                </td>
              </tr>
            )}
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
  const [saving, setSaving] = useState(false);
  const [companyId, setCompanyId] = useState(employee.company_id || "");
  const [buId, setBuId] = useState(employee.bu_id ? String(employee.bu_id) : "");
  const [orgMessage, setOrgMessage] = useState("");

  const [billableMessage, setBillableMessage] = useState("");
  const toggleBillable = async () => {
    setBillableMessage("");
    try {
      await updateEmployeeBillable(employee.id, !employee.is_billable);
      setBillableMessage(employee.is_billable ? "Now non-billable (internal): off the bench" : "Now billable");
      onRefresh();
    } catch (err) {
      setBillableMessage(`Could not change: ${err.message}`);
    }
  };

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
      const data = await getAllocations({ employeeId: employee.id });
      setAllocations(data.filter((a) => a.status === "ACTIVE" || a.status === "PENDING_MARGIN_APPROVAL"));
    } catch (err) {
      console.error("Failed to load allocations:", err);
      setOrgMessage(`Could not load allocations: ${err.message}`);
    } finally {
      setLoadingAllocs(false);
    }
  }, [employee.id]);

  useEffect(() => {
    loadAllocations();
  }, [loadAllocations]);
  const [editingAlloc, setEditingAlloc] = useState(null);
  const [editingDetails, setEditingDetails] = useState(false);
  const canEditEmployee = hasPermission("employees", "edit");
  const [addingAlloc, setAddingAlloc] = useState(false);
  const [allocMessage, setAllocMessage] = useState("");
  const canAllocate = hasPermission("allocations", "create");
  const canEditAllocations = hasPermission("allocations", "edit");
  const afterAllocationChange = () => {
    loadAllocations();
    onRefresh();
  };
  const endAllocationHere = async (alloc) => {
    if (!(await confirmDialog(`End ${employee.first_name}'s allocation to ${alloc.project_name || alloc.client_name}?`))) return;
    setAllocMessage("");
    try {
      await endAllocation(alloc.id);
      afterAllocationChange();
    } catch (err) {
      console.error("[EmployeeDetailModal] Failed to end allocation:", err);
      setAllocMessage(`Could not end the allocation: ${err.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <Card>
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-lg font-semibold">
            {employee.first_name} {employee.last_name}
          </h2>
          <div className="flex items-center gap-1">
            {canEditEmployee && !editingDetails && (
              <Button variant="ghost" size="sm" onClick={() => setEditingDetails(true)}>Edit details</Button>
            )}
            <Button variant="ghost" onClick={onClose}>
              ✕
            </Button>
          </div>
        </div>

        <div className="p-4 space-y-4">
          {editingDetails && (
            <EmployeeDetailsForm employee={employee} onCancel={() => setEditingDetails(false)}
              onSaved={() => { setEditingDetails(false); onRefresh(); }} />
          )}
          {canEditEmployee && <EmploymentActions employee={employee} onChanged={() => onRefresh()} />}
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
              <div className="font-semibold text-gray-700">Employment</div>
              <EmploymentStatus employee={employee} />
            </div>
            <div>
              <div className="font-semibold text-gray-700">Deployment</div>
              <DeploymentStatus employee={employee} />
            </div>
            <div>
              <div className="font-semibold text-gray-700">Allocated</div>
              <div>{employee.allocated_pct}% · {employee.is_billable ? "billable" : "internal (non-billable)"}</div>
              <button type="button" className="text-xs text-blue-700 hover:underline" onClick={toggleBillable}>
                Make {employee.is_billable ? "non-billable (internal)" : "billable"}
              </button>
              {billableMessage ? <div className="text-xs text-gray-600">{billableMessage}</div> : null}
            </div>
            <div>
              <div className="font-semibold text-gray-700">Login</div>
              <div>{employee.has_login ? "Linked" : "None: re-import or add with this email"}</div>
            </div>
            <div>
              <div className="font-semibold text-gray-700">Buddy Program</div>
              <div>{statusLabel(employee.buddy_program_status)}</div>
            </div>
            {!isPast(employee) && (
              <div>
                <div className="font-semibold text-gray-700">Hire-Train-Deploy</div>
                <HtdControl employee={employee} canEdit={canEditEmployee} onChanged={() => onRefresh()} />
              </div>
            )}
            {employee.exit_date && (
              <div>
                <div className="font-semibold text-gray-700">{isPast(employee) ? "Exited" : "Last working day"}</div>
                <div>{employee.exit_date}</div>
              </div>
            )}
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

          <EmployeeCertifications employee={employee} onChanged={onRefresh} />

          <EscalationsPanel employeeId={employee.id} />

          <div className="border-t pt-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-semibold">Current Allocations</h3>
              {canAllocate && !isPast(employee) && (
                <Button variant="secondary" size="sm" onClick={() => setAddingAlloc(true)}>
                  <UserPlus className="h-4 w-4" /> Add allocation
                </Button>
              )}
            </div>
            {allocMessage ? <div className="mb-2 text-sm text-rose-700">{allocMessage}</div> : null}
            {addingAlloc && (
              <div className="mb-3">
                <AllocationForm
                  presetEmployeeId={employee.id}
                  onCancel={() => setAddingAlloc(false)}
                  onSaved={(created) => {
                    setAddingAlloc(false);
                    setAllocMessage(created?.status === "PENDING_MARGIN_APPROVAL"
                      ? `Saved, waiting for margin approval: ${created.margin?.message || ""}` : "");
                    afterAllocationChange();
                  }}
                />
              </div>
            )}
            {loadingAllocs ? (
              <div className="text-gray-500 text-sm">Loading allocations...</div>
            ) : allocations.length === 0 ? (
              <div className="text-gray-500 text-sm">No active allocations</div>
            ) : (
              <div className="space-y-2">
                {allocations.map((alloc) => (
                  <div key={alloc.id} className="flex items-start justify-between gap-2 rounded border p-2 bg-gray-50 text-sm">
                    <div className="space-y-0.5">
                      <div className="font-semibold">
                        {alloc.project_id ? (
                          <Link to={`/projects?project=${alloc.project_id}`} className="text-blue-700 hover:underline">
                            {alloc.project_name || "Project"}
                          </Link>
                        ) : <span className="text-amber-700">No project</span>}
                        {" · "}{alloc.client_name}
                      </div>
                      <div className="text-gray-600">{alloc.demand_job_title}</div>
                      <div className="text-gray-600">
                        {alloc.utilization_pct}% allocation, from {alloc.start_date}
                        {alloc.end_date ? ` to ${alloc.end_date}` : " (open-ended)"}
                      </div>
                      <AllocationState alloc={alloc} />
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditingAlloc(alloc)}>
                        {alloc.status !== "ACTIVE" ? "Review" : canEditAllocations ? "Extend / Edit" : "History"}
                      </Button>
                      {alloc.status === "ACTIVE" && canAllocate && (
                        <Button variant="ghost" size="sm" onClick={() => endAllocationHere(alloc)}>End</Button>
                      )}
                    </div>
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
        {editingAlloc && (
          <AllocationEditModal allocation={editingAlloc} onClose={() => setEditingAlloc(null)} onSaved={afterAllocationChange} />
        )}
      </Card>
      </div>
    </div>
  );
}

const ALLOCATION_STATUS_TONE = {
  ACTIVE: "bg-emerald-100 text-emerald-800",
  PENDING_MARGIN_APPROVAL: "bg-amber-100 text-amber-800",
  MARGIN_REJECTED: "bg-rose-100 text-rose-800",
};

function AllocationsTab() {
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(null);
  const [searchParams] = useSearchParams();
  // the margin-approval task opens ?tab=allocations&allocation=<id>
  const focusId = searchParams.get("allocation");
  const canEdit = hasPermission("allocations", "edit");

  useEffect(() => {
    loadAllocations();
  }, []);

  const loadAllocations = async () => {
    setLoading(true);
    setError("");
    try {
      setAllocations(await getAllocations());
    } catch (err) {
      setError(err.message || "Failed to load allocations");
    } finally {
      setLoading(false);
    }
  };

  // open the focused allocation once (closing it must not reopen it on the next reload)
  const [focusHandled, setFocusHandled] = useState(false);
  useEffect(() => {
    if (!focusId || loading || focusHandled) return;
    const focused = allocations.find((a) => a.id === focusId);
    if (focused) setEditing(focused);
    setFocusHandled(true);
  }, [focusId, loading, allocations, focusHandled]);

  if (loading) return <div className="py-8 text-center text-gray-500">Loading allocations...</div>;

  return (
    <div className="space-y-4">
      {notice && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{notice}</div>
      )}
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
              <th className="px-4 py-2 text-left font-semibold">Bill Rate</th>
              <th className="px-4 py-2 text-left font-semibold">Margin</th>
              <th className="px-4 py-2 text-left font-semibold">Status</th>
              <th className="px-4 py-2 text-left font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {allocations.map((alloc) => (
              <tr key={alloc.id} className={cx("border-b hover:bg-gray-50", alloc.id === focusId && "bg-amber-50")}>
                <td className="px-4 py-2">{alloc.employee_name || "—"}</td>
                <td className="px-4 py-2">
                  {alloc.project_id ? (
                    <Link to={`/projects?project=${alloc.project_id}`} className="text-blue-700 hover:underline">
                      {alloc.project_name || "Project"}
                    </Link>
                  ) : "—"}
                </td>
                <td className="px-4 py-2">{alloc.utilization_pct}%</td>
                <td className="px-4 py-2 text-gray-600">{alloc.start_date || "—"}</td>
                <td className="px-4 py-2 text-gray-600">{alloc.end_date || "Ongoing"}</td>
                <td className="px-4 py-2 text-gray-600">
                  {alloc.billing_rate_usd_cents ? `$${(alloc.billing_rate_usd_cents / 100).toFixed(2)}/h` : "—"}
                </td>
                <td className="px-4 py-2 text-gray-600" title={alloc.margin_check || "placed before the margin guard"}>
                  {marginLabel(alloc.margin_pct)}
                </td>
                <td className="px-4 py-2">
                  <AllocationState alloc={alloc} />
                  {alloc.pending_change && alloc.status === "ACTIVE" && (
                    <div className="mt-1 text-xs font-semibold text-amber-700">Change awaiting approval</div>
                  )}
                </td>
                <td className="px-4 py-2 space-x-1">
                  {(alloc.status === "ACTIVE" || alloc.pending_change) && (
                    <Button variant="ghost" size="sm" onClick={() => setEditing(alloc)}>
                      {alloc.pending_change ? "Review" : canEdit ? "Extend / Edit" : "History"}
                    </Button>
                  )}
                  {alloc.status === "ACTIVE" && (
                    <Button variant="ghost" size="sm" onClick={() => handleEndAllocation(alloc.id)}>
                      End
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <AllocationForm
          onCancel={() => setShowForm(false)}
          onSaved={(created) => {
            setShowForm(false);
            const flags = created?.margin?.flags || [];
            if (created?.status === "PENDING_MARGIN_APPROVAL") {
              setNotice(`Saved, waiting for margin approval: ${created.margin?.message || ""}`);
            } else if (flags.includes("NO_MARGIN_FLOOR_CONFIGURED")) {
              setNotice("Saved. No margin floor is configured for this placement (P&L > Rate Card).");
            } else {
              setNotice("");
            }
            loadAllocations();
          }}
        />
      )}
      {editing && (
        <AllocationEditModal allocation={editing} onClose={() => setEditing(null)} onSaved={loadAllocations} />
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
  const [error, setError] = useState("");

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAllEmployees();
      setEmployees((data || []).filter((e) => !isPast(e)));
    } catch (err) {
      console.error("[Resources] Failed to load employees:", err);
      setError(err.message || "Failed to load employees");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEmployees();
  }, [loadEmployees]);

  if (loading) return <div className="py-8 text-center text-gray-500">Loading resources...</div>;
  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
        <AlertCircle className="mb-1 inline h-4 w-4" /> {error}
      </div>
    );
  }

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
              const utilization = emp.allocated_pct || 0;
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
          <h4 className="font-semibold mb-3">Headcount</h4>
          <div className="text-sm text-gray-600">
            <div className="mb-2">On the payroll: {employees.filter((e) => ON_PAYROLL.has(e.employment_status)).length}</div>
            <div>Joining: {employees.filter((e) => e.employment_status === "JOINING").length}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

const EMPLOYEE_TABS = ["list", "past", "allocations", "resources"];

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
          onClick={() => setActiveTab("past")}
          className={cx(
            "px-4 py-2 font-medium border-b-2",
            activeTab === "past"
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          )}
        >
          <UserX className="inline h-4 w-4 mr-2" />
          Past Employees
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
        {activeTab === "past" && <EmployeeListTab past />}
        {activeTab === "allocations" && <AllocationsTab />}
        {activeTab === "resources" && <ResourcesTab />}
      </div>
    </div>
  );
}
