// The one form for allocating an employee. Used by the Allocations, Employees (employee preset) and
// Projects (project preset) screens. Two kinds of placement (CEO 2026-10-24):
// - Staff Aug: pick the client job (the requisition); it brings its client, project and client bill
//   rate along, and the bill rate can be overridden here.
// - Project work: pick the project; type the role and the bill rate (there is no job behind it).
import { useEffect, useMemo, useState } from "react";
import { Button, Input, Select } from "./ui";
import cx from "../utils/cx";
import { createAllocation, getAllocationDropdowns } from "../services/api/allocations";
import { MarginLine, useMarginPreview } from "./AllocationMargin";
import { getClientContacts } from "../services/api/clients";
import { listWorkOrders } from "../services/api/workOrders";

const MODES = [["job", "Client job (Staff Aug)"], ["project", "Project"]];

export default function AllocationForm({ presetEmployeeId, presetProjectId, onCancel, onSaved }) {
  const [mode, setMode] = useState(presetProjectId ? "project" : "job");
  const [employeeId, setEmployeeId] = useState(presetEmployeeId || "");
  const [jobId, setJobId] = useState("");
  const [projectId, setProjectId] = useState(presetProjectId || "");
  const [role, setRole] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [billRate, setBillRate] = useState("");
  const [allowConcurrent, setAllowConcurrent] = useState(false);
  const [billable, setBillable] = useState(""); // "" = from the project
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [projects, setProjects] = useState([]);
  // the client's timesheet approver for this placement and the client PO it bills against
  const [approverEmail, setApproverEmail] = useState("");
  const [workOrderId, setWorkOrderId] = useState("");
  const [approverContacts, setApproverContacts] = useState([]);
  const [workOrders, setWorkOrders] = useState([]);

  useEffect(() => {
    getAllocationDropdowns()
      .then((data) => {
        setEmployees(
          (data?.employees || [])
            .map((e) => ({ value: e.id, label: e.name }))
            .sort((a, b) => a.label.localeCompare(b.label)),
        );
        setJobs(data?.demands || []);
        setProjects(data?.projects || []);
      })
      .catch((err) => setError(`Could not load employees, jobs and projects: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  const jobOptions = useMemo(
    () => jobs
      .filter((j) => !presetProjectId || j.project_id === presetProjectId)
      .map((j) => ({
        value: j.id,
        label: [j.name, j.client_name, j.project_name].filter(Boolean).join(" · "),
      })),
    [jobs, presetProjectId],
  );
  const projectOptions = useMemo(
    () => projects.map((p) => ({ value: p.id, label: [p.name, p.client_name].filter(Boolean).join(" · ") })),
    [projects],
  );
  const job = mode === "job" ? jobs.find((j) => j.id === jobId) : null;
  const project = mode === "project" ? projects.find((p) => p.id === projectId) : null;
  const target = mode === "job" ? jobId : projectId;
  const rateCents = billRate ? Math.round(parseFloat(billRate) * 100) : undefined;
  // live margin against the rate card while the terms are typed (the server re-checks on save)
  const { margin, error: marginError } = useMarginPreview({
    employeeId,
    demandId: mode === "job" ? jobId : undefined,
    projectId: mode === "project" ? projectId : (presetProjectId || job?.project_id || undefined),
    billingRateUsdCents: rateCents,
    billable: billable === "" ? undefined : billable === "yes",
    startDate: startDate || undefined,
    role: mode === "project" ? role : undefined,
  }, Boolean(employeeId && target));
  const clientId = job?.client_id || project?.client_id;

  useEffect(() => {
    setApproverContacts([]);
    setWorkOrders([]);
    if (!clientId) return;
    getClientContacts(clientId)
      .then((data) => setApproverContacts((data?.contacts || []).filter((c) => c.role_type === "TIMESHEET_APPROVER")))
      .catch((err) => setError(`Could not load the client's contacts: ${err.message}`));
    listWorkOrders({ clientId })
      .then((list) => setWorkOrders(list.filter((w) => w.status !== "ENDED")))
      .catch((err) => setError(`Could not load the client's work orders: ${err.message}`));
  }, [clientId]);

  const switchMode = (next) => {
    setMode(next);
    setApproverEmail("");
    setWorkOrderId("");
    setBillRate("");
    setError("");
  };

  const pickJob = (id) => {
    setJobId(id);
    setApproverEmail("");
    setWorkOrderId("");
    const picked = jobs.find((j) => j.id === id);
    setBillRate(picked?.billing_rate_usd_cents ? String(picked.billing_rate_usd_cents / 100) : "");
  };

  const handleSave = async () => {
    if (!employeeId || !target) {
      setError(mode === "job" ? "Pick the employee and the client job." : "Pick the employee and the project.");
      return;
    }
    if (mode === "project" && !role.trim()) {
      setError("Enter the role on the project.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const created = await createAllocation({
        employeeId,
        demandId: mode === "job" ? jobId : undefined,
        projectId: mode === "project" ? projectId : (presetProjectId || job?.project_id || undefined),
        role: mode === "project" ? role.trim() : undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        utilizationPct: utilizationPct ? Number(utilizationPct) : undefined,
        billingRateUsdCents: rateCents,
        allowConcurrent,
        billable: billable === "" ? undefined : billable === "yes",
        timesheetApproverEmail: approverEmail || undefined,
        workOrderId: workOrderId || undefined,
      });
      onSaved(created);
    } catch (err) {
      setError(err.message || "Allocation blocked.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="mb-6 rounded-2xl border border-gray-200 bg-gray-50 p-4 text-center text-sm text-gray-500">Loading…</div>;
  }

  return (
    <div className="mb-6 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-gray-900">Allocate to</span>
        {MODES.map(([key, label]) => (
          <button key={key} type="button" onClick={() => switchMode(key)}
            className={cx("rounded-lg px-3 py-1 text-sm font-semibold",
              mode === key ? "bg-bx-navy text-white" : "border bg-white text-gray-700 hover:bg-gray-100")}>
            {label}
          </button>
        ))}
      </div>
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}
      {mode === "job" && jobOptions.length === 0 && (
        <div className="mb-4 text-sm text-amber-700">
          No open client jobs{presetProjectId ? " for this project" : ""}. Create a job for the client on the Jobs screen, or allocate to the project.
        </div>
      )}
      {mode === "project" && projectOptions.length === 0 && (
        <div className="mb-4 text-sm text-amber-700">No live projects. Create the project (with its client) on the Projects screen first.</div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {!presetEmployeeId && (
          <Select label="Employee" value={employeeId} onChange={setEmployeeId} options={employees} placeholder="Select employee" />
        )}
        {mode === "job" ? (
          <Select label="Client job" value={jobId} onChange={pickJob} options={jobOptions} placeholder="Select job" />
        ) : (
          <>
            <Select label="Project" value={projectId} onChange={setProjectId} options={projectOptions} placeholder="Select project" />
            <Input label="Role on the project *" value={role} onChange={setRole} placeholder="e.g. Integration Lead" />
          </>
        )}
        <Input label={mode === "project" ? "Bill rate (USD / hour) *" : "Bill rate (USD / hour)"} type="number"
          value={billRate} onChange={setBillRate} placeholder={mode === "project" ? "required for billable work" : "from the job"} />
        <Input label="Start Date" type="date" value={startDate} onChange={setStartDate} />
        <Input label="End Date" type="date" value={endDate} onChange={setEndDate} />
        <Input label="Utilization %" type="number" value={utilizationPct} onChange={setUtilizationPct} placeholder="100" />
        <Select
          label="Billable time?"
          value={billable}
          onChange={setBillable}
          options={[{ value: "", label: "From the project" }, { value: "yes", label: "Billable" },
            { value: "no", label: "Non-billable (never invoiced)" }]}
        />
        {approverContacts.length ? (
          <Select
            label="Client timesheet approver"
            value={approverEmail}
            onChange={setApproverEmail}
            options={[{ value: "", label: "None" },
              ...approverContacts.map((c) => ({ value: c.email.toLowerCase(), label: `${c.name} (${c.email})` }))]}
          />
        ) : (
          <Input label="Client timesheet approver email" value={approverEmail} onChange={setApproverEmail}
            placeholder="optional" />
        )}
        <Select
          label="Client PO (work order)"
          value={workOrderId}
          onChange={setWorkOrderId}
          options={[{ value: "", label: workOrders.length ? "None" : "No work orders for this client" },
            ...workOrders.map((w) => ({ value: w.id, label: `${w.po_number}${w.end_date ? ` (ends ${w.end_date})` : ""}` }))]}
        />
      </div>
      {job && (
        <div className="mt-2 text-xs text-gray-600">
          Client: {job.client_name || "—"} · Project: {job.project_name || "none on the job"}
        </div>
      )}
      {project && (
        <div className="mt-2 text-xs text-gray-600">
          Client: {project.client_name || "—"} · {project.delivery_engine === "CORE" ? "Core project (needs a Core-certified consultant)" : "Speciality project"}
        </div>
      )}
      <MarginLine margin={margin} error={marginError} />
      <label className="mt-3 flex items-center gap-2 text-xs text-gray-700">
        <input type="checkbox" checked={allowConcurrent} onChange={(e) => setAllowConcurrent(e.target.checked)} />
        Allow concurrent (multiple active allocations at once)
      </label>
      <div className="mt-4 flex gap-2">
        <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save Allocation"}</Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>Cancel</Button>
      </div>
    </div>
  );
}
