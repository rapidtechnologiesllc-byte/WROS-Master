// The one form for allocating an employee to a client job. Used by the
// Allocations, Employees (employee preset) and Projects (project preset)
// screens. A job is the requisition: picking it brings its client, project
// and client bill rate along; the bill rate can be overridden here.
import { useEffect, useMemo, useState } from "react";
import { Button, Input, Select } from "./ui";
import { createAllocation, getAllocationDropdowns } from "../services/api/allocations";

export default function AllocationForm({ presetEmployeeId, presetProjectId, onCancel, onSaved }) {
  const [employeeId, setEmployeeId] = useState(presetEmployeeId || "");
  const [jobId, setJobId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [utilizationPct, setUtilizationPct] = useState("100");
  const [billRate, setBillRate] = useState("");
  const [allowConcurrent, setAllowConcurrent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    getAllocationDropdowns()
      .then((data) => {
        setEmployees(
          (data?.employees || [])
            .map((e) => ({ value: e.id, label: e.name }))
            .sort((a, b) => a.label.localeCompare(b.label)),
        );
        setJobs(data?.demands || []);
      })
      .catch((err) => setError(`Could not load employees and jobs: ${err.message}`))
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
  const job = jobs.find((j) => j.id === jobId);

  const pickJob = (id) => {
    setJobId(id);
    const picked = jobs.find((j) => j.id === id);
    setBillRate(picked?.billing_rate_usd_cents ? String(picked.billing_rate_usd_cents / 100) : "");
  };

  const handleSave = async () => {
    if (!employeeId || !jobId) {
      setError("Pick the employee and the client job.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await createAllocation({
        employeeId,
        demandId: jobId,
        projectId: presetProjectId || job?.project_id || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        utilizationPct: utilizationPct ? Number(utilizationPct) : undefined,
        billingRateUsdCents: billRate ? Math.round(parseFloat(billRate) * 100) : undefined,
        allowConcurrent,
      });
      onSaved();
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
      <div className="mb-4 text-sm font-semibold text-gray-900">Allocate to a client job</div>
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}
      {jobOptions.length === 0 && (
        <div className="mb-4 text-sm text-amber-700">
          No open client jobs{presetProjectId ? " for this project" : ""}. Create a job for the client (with its project) on the Jobs screen first.
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {!presetEmployeeId && (
          <Select label="Employee" value={employeeId} onChange={setEmployeeId} options={employees} placeholder="Select employee" />
        )}
        <Select label="Client job" value={jobId} onChange={pickJob} options={jobOptions} placeholder="Select job" />
        <Input label="Bill rate (USD / hour)" type="number" value={billRate} onChange={setBillRate} placeholder="from the job" />
        <Input label="Start Date" type="date" value={startDate} onChange={setStartDate} />
        <Input label="End Date" type="date" value={endDate} onChange={setEndDate} />
        <Input label="Utilization %" type="number" value={utilizationPct} onChange={setUtilizationPct} placeholder="100" />
      </div>
      {job && (
        <div className="mt-2 text-xs text-gray-600">
          Client: {job.client_name || "—"} · Project: {job.project_name || "none on the job"}
        </div>
      )}
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
