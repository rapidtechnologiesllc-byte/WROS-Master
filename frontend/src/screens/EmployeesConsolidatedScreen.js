// DEFECT-2: Consolidated Employees Screen
// Consolidates EmployeeDirectoryScreen + ResourceManagementScreen + AllocationsScreen
// Employee List: current employees (headcount, employment + deployment, filters/sort in the URL), Import + Add
// Past Employees: terminated people, never in the headcount
// Allocations: manage employee allocations, assign to projects
// Resources: availability heatmap of current employees

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Users, UserX, Briefcase, Grid3x3, UserPlus, RefreshCw, AlertCircle, Upload, Download } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { pill } from "../utils/pill";
import useTabParam from "../utils/useTabParam";
import { getAllEmployees } from "../services/api/employees";
import { apiRequest } from "../services/api/client";
import { getAllocations, endAllocation } from "../services/api/allocations";
import AllocationForm from "../components/AllocationForm";
import AllocationEditModal from "../components/AllocationEditModal";
import { marginLabel } from "../components/AllocationMargin";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import { AddEmployeeModal, ImportEmployeesModal } from "../components/EmployeeImport";
import {
  AllocationState, DEPLOYMENT, DeploymentStatus, EMPLOYMENT, EmploymentStatus, ON_PAYROLL, TONE, fullName, isPast,
  statusLabel,
} from "../components/EmployeeStatus";
import { confirmDialog } from "../utils/dialogs";

// Our companies (Users & Access Control > Companies) and business units
const COMPANIES_PATH = "/api/v1/api/admin/users-access-control/delivery-centers";
const loadOrgOptions = () => Promise.all([apiRequest(COMPANIES_PATH), apiRequest("/rbac/business-units")])
  .then(([c, b]) => ({ companies: c.data?.delivery_centers || [], businessUnits: b.data?.business_units || [] }));

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


// Sort keys -> the value compared (strings case-insensitively, numbers numerically)
const SORTERS = {
  number: (e) => e.employee_number || "",
  name: (e) => fullName(e).toLowerCase(),
  manager: (e) => (e.reporting_manager_name || "").toLowerCase(),
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

// The list as shown (filters and sort applied) as a CSV file
function downloadCsv(rows, org, past) {
  const columns = [
    ["Employee No.", (e) => e.employee_number], ["Name", fullName], ["Email", (e) => e.email],
    ["Job Title", (e) => e.current_title], ["Company", (e) => org.companyName(e.company_id)],
    ["Business Unit", (e) => org.buName(e.bu_id)], ["Reporting To", (e) => e.reporting_manager_name],
    ["Location", (e) => statusLabel(e.work_location)], ["Date of Joining", (e) => e.joining_date],
    ...(past ? [["Exit Date", (e) => e.exit_date]] : [
      ["Employment", (e) => (EMPLOYMENT[e.employment_status] || [e.employment_status])[0]],
      ["Deployment", (e) => (DEPLOYMENT[e.deployment_status] || [e.deployment_status || ""])[0]],
      ["Billable", (e) => (e.is_billable ? "Billable" : "Internal")], ["Allocated %", (e) => e.allocated_pct],
    ]),
  ];
  const cell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const csv = [columns.map(([title]) => cell(title)).join(","),
    ...rows.map((e) => columns.map(([, get]) => cell(get(e))).join(","))].join("\r\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  link.download = `${past ? "past-employees" : "employees"}-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function EmployeeListTab({ past = false }) {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
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

  // /employees?employee=<id> (the import results link) opens that employee's profile
  const navigate = useNavigate();
  useEffect(() => {
    if (linkedEmployeeId) navigate(`/employees/${linkedEmployeeId}`, { replace: true });
  }, [linkedEmployeeId, navigate]);

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
        <Button variant="ghost" onClick={() => downloadCsv(rows, org, past)} title="Download this list (CSV)" disabled={!rows.length}>
          <Download className="h-4 w-4" />
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
              <SortHeader label="Emp. No." sortKey="number" sort={sort} dir={dir} onSort={onSort} />
              <SortHeader label="Name" sortKey="name" sort={sort} dir={dir} onSort={onSort} />
              <th className="px-4 py-2 text-left font-semibold">Job Title</th>
              <SortHeader label="Company" sortKey="company" sort={sort} dir={dir} onSort={onSort} />
              <SortHeader label="Business Unit" sortKey="bu" sort={sort} dir={dir} onSort={onSort} />
              <SortHeader label="Reporting To" sortKey="manager" sort={sort} dir={dir} onSort={onSort} />
              {past ? (
                <>
                  <SortHeader label="Joined" sortKey="joined" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Exited" sortKey="exited" sort={sort} dir={dir} onSort={onSort} />
                </>
              ) : (
                <>
                  <SortHeader label="Joined" sortKey="joined" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Employment" sortKey="employment" sort={sort} dir={dir} onSort={onSort} />
                  <SortHeader label="Deployment" sortKey="deployment" sort={sort} dir={dir} onSort={onSort} />
                  <th className="px-4 py-2 text-left font-semibold">Billable</th>
                  <SortHeader label="Allocated" sortKey="allocated" sort={sort} dir={dir} onSort={onSort} />
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((emp) => (
              <tr key={emp.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-2 whitespace-nowrap">
                  <Link to={`/employees/${emp.id}`} className="font-medium text-blue-700 hover:underline">
                    {emp.employee_number || "—"}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <Link to={`/employees/${emp.id}`} className="font-medium text-blue-700 hover:underline">{fullName(emp)}</Link>
                  <div className="text-xs text-gray-500">{emp.email}</div>
                </td>
                <td className="px-4 py-2">{emp.current_title || "—"}</td>
                <td className="px-4 py-2">{org.companyName(emp.company_id) || <span className="text-amber-700">Not set</span>}</td>
                <td className="px-4 py-2">{org.buName(emp.bu_id) || "—"}</td>
                <td className="px-4 py-2">
                  {emp.reporting_manager_employee_id ? (
                    <Link to={`/employees/${emp.reporting_manager_employee_id}`} className="text-blue-700 hover:underline">
                      {emp.reporting_manager_name}
                    </Link>
                  ) : emp.reporting_manager_name || "—"}
                </td>
                {past ? (
                  <>
                    <td className="px-4 py-2 whitespace-nowrap">{emp.joining_date || "—"}</td>
                    <td className="px-4 py-2 whitespace-nowrap">{emp.exit_date || "—"}</td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2 whitespace-nowrap">{emp.joining_date || "—"}</td>
                    <td className="px-4 py-2">
                      <EmploymentStatus employee={emp} />
                      {!emp.has_login ? <div className="text-xs text-amber-700">no login</div> : null}
                    </td>
                    <td className="px-4 py-2"><DeploymentStatus employee={emp} /></td>
                    <td className="px-4 py-2">{emp.is_billable ? "Billable" : "Internal"}</td>
                    <td className="px-4 py-2">{emp.allocated_pct}%</td>
                  </>
                )}
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={past ? 8 : 11} className="px-4 py-8 text-center text-gray-500">
                  {population.length ? "No one matches these filters." : past ? "No past employees." : "No employees yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

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
