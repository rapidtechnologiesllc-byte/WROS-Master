// The one form for allocating an employee. Used by the Allocations, Employees (employee preset) and
// Projects (project preset) screens. Two kinds of placement (CEO 2026-10-24):
// - Staff Aug (one person's time and materials at a client): pick the client (required), then
//   optionally one of that client's jobs. A job brings its bill rate along (it can be overridden
//   here). With no job -- an existing placement recorded after the fact (CEO 2026-11-11) -- type
//   the role and the bill rate; the time is invoiced to the client directly.
// - Project work (defined scope): pick the project; type the role and the bill rate.
// The bill rate is entered as agreed with the client: an amount in a currency (the client's by
// default: its location's -- India INR, US USD) per hour, month or year. The server values it in
// USD per hour for the margin and the P&L; the invoice is in the client's currency.
import { useEffect, useMemo, useState } from "react";
import { Button, Input, Select } from "./ui";
import cx from "../utils/cx";
import { createAllocation, getAllocationDropdowns } from "../services/api/allocations";
import { MarginLine, useMarginPreview } from "./AllocationMargin";
import { getClientContacts } from "../services/api/clients";
import { listWorkOrders } from "../services/api/workOrders";

const MODES = [["job", "Client (Staff Aug)"], ["project", "Project"]];
const BASIS_LABELS = { HOURLY: "per hour", MONTHLY: "per month", ANNUAL: "per year" };
const DEFAULT_BASIS = "HOURLY";

// Amount + currency + per hour / month / year, in one field
function BillRateField({ label, amount, onAmount, currency, onCurrency, basis, onBasis, currencies, bases, placeholder }) {
  const select = "border-l border-gray-300 bg-white px-1 py-2 text-sm text-gray-900 outline-none";
  return (
    <div className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <div className="flex flex-wrap overflow-hidden rounded-xl border bg-white transition focus-within:border-gray-900">
        <input type="number" min="0" step="0.01" value={amount} placeholder={placeholder} aria-label="Bill rate amount"
          onChange={(e) => onAmount(e.target.value)}
          className="min-w-[6rem] flex-1 border-0 bg-white px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400" />
        <select value={currency} onChange={(e) => onCurrency(e.target.value)} aria-label="Bill rate currency" className={select}>
          {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={basis} onChange={(e) => onBasis(e.target.value)} aria-label="Bill rate period" className={select}>
          {bases.map((b) => <option key={b} value={b}>{BASIS_LABELS[b] || b}</option>)}
        </select>
      </div>
    </div>
  );
}

export default function AllocationForm({ presetEmployeeId, presetProjectId, onCancel, onSaved }) {
  const [mode, setMode] = useState(presetProjectId ? "project" : "job");
  const [employeeId, setEmployeeId] = useState(presetEmployeeId || "");
  const [staffAugClientId, setStaffAugClientId] = useState("");
  const [jobId, setJobId] = useState("");
  const [projectId, setProjectId] = useState(presetProjectId || "");
  const [role, setRole] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [billRate, setBillRate] = useState("");
  const [rateCurrency, setRateCurrency] = useState("USD");
  const [rateBasis, setRateBasis] = useState(DEFAULT_BASIS);
  const [rateCurrencies, setRateCurrencies] = useState(["USD"]);
  const [rateBases, setRateBases] = useState([DEFAULT_BASIS]);
  const [allowConcurrent, setAllowConcurrent] = useState(false);
  const [billable, setBillable] = useState(""); // "" = from the project
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
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
        setClients((data?.clients || []).map((c) => ({ value: c.id, label: c.name, currency: c.currency })));
        if (data?.rate_currencies?.length) setRateCurrencies(data.rate_currencies);
        if (data?.rate_bases?.length) setRateBases(data.rate_bases);
        // opened from a project: Staff Aug there is at the project's client
        const preset = (data?.projects || []).find((p) => p.id === presetProjectId);
        if (preset?.client_id) {
          setStaffAugClientId(preset.client_id);
          const presetClient = (data?.clients || []).find((c) => c.id === preset.client_id);
          if (presetClient?.currency) setRateCurrency(presetClient.currency);
        }
      })
      .catch((err) => setError(`Could not load employees, jobs and projects: ${err.message}`))
      .finally(() => setLoading(false));
  }, [presetProjectId]);

  // only the picked client's jobs
  const clientJobs = useMemo(
    () => jobs.filter((j) => j.client_id === staffAugClientId && (!presetProjectId || j.project_id === presetProjectId)),
    [jobs, staffAugClientId, presetProjectId],
  );
  const jobOptions = useMemo(
    () => [
      { value: "", label: !staffAugClientId ? "Pick the client first"
        : clientJobs.length ? "No job (existing placement)" : "No open jobs for this client" },
      ...clientJobs.map((j) => ({ value: j.id, label: [j.name, j.project_name].filter(Boolean).join(" · ") })),
    ],
    [clientJobs, staffAugClientId],
  );
  const projectOptions = useMemo(
    () => projects.map((p) => ({ value: p.id, label: [p.name, p.client_name].filter(Boolean).join(" · ") })),
    [projects],
  );
  const job = mode === "job" ? jobs.find((j) => j.id === jobId) : null;
  const project = mode === "project" ? projects.find((p) => p.id === projectId) : null;
  const target = mode === "job" ? staffAugClientId : projectId;
  // no job behind the placement: the role and the bill rate are typed here
  const needsRole = mode === "project" || !jobId;
  // the rate as agreed: amount in minor units, its currency and per hour / month / year
  const rateCents = billRate ? Math.round(parseFloat(billRate) * 100) : undefined;
  const agreedRate = rateCents
    ? { billRateAmountCents: rateCents, billRateCurrency: rateCurrency, billRateBasis: rateBasis }
    : {};
  const currencyOf = (id) => clients.find((c) => c.value === id)?.currency || "USD";
  // live margin against the rate card while the terms are typed (the server re-checks on save)
  const { margin, error: marginError } = useMarginPreview({
    employeeId,
    clientId: mode === "job" ? staffAugClientId : undefined,
    demandId: mode === "job" ? jobId : undefined,
    projectId: mode === "project" ? projectId : (job?.project_id || undefined),
    ...agreedRate,
    billable: billable === "" ? undefined : billable === "yes",
    startDate: startDate || undefined,
    role: needsRole ? role : undefined,
  }, Boolean(employeeId && target));
  const clientId = mode === "job" ? staffAugClientId : project?.client_id;

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

  const resetRate = (currency) => {
    setBillRate("");
    setRateCurrency(currency || "USD");
    setRateBasis(DEFAULT_BASIS);
  };

  const switchMode = (next) => {
    setMode(next);
    setApproverEmail("");
    setWorkOrderId("");
    const nextClient = next === "job" ? staffAugClientId : projects.find((p) => p.id === projectId)?.client_id;
    resetRate(currencyOf(nextClient));
    setError("");
  };

  const pickProject = (id) => {
    setProjectId(id);
    setRateCurrency(currencyOf(projects.find((p) => p.id === id)?.client_id));
  };

  const pickClient = (id) => {
    setStaffAugClientId(id);
    setJobId("");
    setApproverEmail("");
    setWorkOrderId("");
    resetRate(currencyOf(id));  // the client's currency: what it is invoiced in
  };

  const pickJob = (id) => {
    setJobId(id);
    setApproverEmail("");
    setWorkOrderId("");
    const picked = jobs.find((j) => j.id === id);
    if (picked?.billing_rate_usd_cents) {
      // the job's client bill rate is kept in USD per hour
      setBillRate(String(picked.billing_rate_usd_cents / 100));
      setRateCurrency("USD");
      setRateBasis(DEFAULT_BASIS);
    } else {
      resetRate(currencyOf(staffAugClientId));
    }
  };

  const handleSave = async () => {
    if (!employeeId || !target) {
      setError(mode === "job" ? "Pick the employee and the client." : "Pick the employee and the project.");
      return;
    }
    if (needsRole && !role.trim()) {
      setError(mode === "project" ? "Enter the role on the project." : "Enter the role at the client (there is no job to take it from).");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const created = await createAllocation({
        employeeId,
        clientId: mode === "job" ? staffAugClientId : undefined,
        demandId: mode === "job" ? (jobId || undefined) : undefined,
        projectId: mode === "project" ? projectId : (job?.project_id || undefined),
        role: needsRole ? role.trim() : undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        utilizationPct: utilizationPct ? Number(utilizationPct) : undefined,
        ...agreedRate,
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
      {mode === "job" && clients.length === 0 && (
        <div className="mb-4 text-sm text-amber-700">No clients yet. Add the client on the Clients screen first.</div>
      )}
      {mode === "project" && projectOptions.length === 0 && (
        <div className="mb-4 text-sm text-amber-700">No live projects. Create the project (with its client) on the Projects screen first.</div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {!presetEmployeeId && (
          <Select label="Employee" value={employeeId} onChange={setEmployeeId} options={employees} placeholder="Select employee" />
        )}
        {mode === "job" ? (
          <>
            <Select label="Client *" value={staffAugClientId} onChange={pickClient} options={clients} />
            <Select label="Client job (optional)" value={jobId} onChange={pickJob} options={jobOptions}
              disabled={!staffAugClientId} />
            {!jobId && (
              <Input label="Role at the client *" value={role} onChange={setRole} placeholder="e.g. Guidewire Developer" />
            )}
          </>
        ) : (
          <>
            <Select label="Project" value={projectId} onChange={pickProject} options={projectOptions} placeholder="Select project" />
            <Input label="Role on the project *" value={role} onChange={setRole} placeholder="e.g. Integration Lead" />
          </>
        )}
        <BillRateField label={needsRole ? "Bill rate *" : "Bill rate"} amount={billRate} onAmount={setBillRate}
          currency={rateCurrency} onCurrency={setRateCurrency} basis={rateBasis} onBasis={setRateBasis}
          currencies={rateCurrencies} bases={rateBases}
          placeholder={needsRole ? "required for billable work" : "from the job"} />
        <Input label="Start Date" type="date" value={startDate} onChange={setStartDate} />
        <Input label="End Date" type="date" value={endDate} onChange={setEndDate} />
        <Input label="Utilization %" type="number" value={utilizationPct} onChange={setUtilizationPct} placeholder="100" />
        <Select
          label="Billable time?"
          value={billable}
          onChange={setBillable}
          options={[{ value: "", label: mode === "job" && !job?.project_id ? "Billable (default)" : "From the project" },
            { value: "yes", label: "Billable" },
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
      {mode === "job" && staffAugClientId && (
        <div className="mt-2 text-xs text-gray-600">
          {job
            ? (job.project_name ? `Invoiced through the job's project: ${job.project_name}.` : "Time and materials, invoiced to the client.")
            : "No job: an existing placement. Time and materials at the role and bill rate above, invoiced to the client."}
        </div>
      )}
      {project && (
        <div className="mt-2 text-xs text-gray-600">
          Client: {project.client_name || "—"} · {project.delivery_engine === "CORE" ? "Direct project (needs a Direct-certified consultant)" : "Speciality project"}
        </div>
      )}
      {rateCents && margin?.bill_rate_usd_cents && (rateCurrency !== "USD" || rateBasis !== DEFAULT_BASIS) ? (
        <div className="mt-2 text-xs text-gray-600">
          Billed by the hour: {rateCurrency} {Number(billRate).toLocaleString()} {BASIS_LABELS[rateBasis]} is valued at
          ${(margin.bill_rate_usd_cents / 100).toFixed(2)} per hour for the margin and the P&L.
          {clientId ? ` The client is invoiced in ${currencyOf(clientId)}.` : ""}
        </div>
      ) : null}
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
