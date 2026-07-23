// S-245 (Create Employee Profile) + S-246 (Mark Employee as Bench) +
// S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report).
import { useEffect, useRef, useState } from "react";
import { UserPlus, RefreshCw, AlertTriangle, LogOut, LogIn, ArrowRightLeft, Upload, History, Award, LineChart, Flag, CheckCircle2 } from "lucide-react";
import { Card, Button, Input, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  createEmployee,
  getAllEmployees,
  getBenchAgingAlerts,
  markEmployeeOnBench,
  removeEmployeeFromBench,
  convertCandidateToEmployee,
  bulkImportEmployees,
  getEngineHistory,
  getEmployeePerformance,
} from "../services/api/employees";
import {
  createEmployeeMilestone,
  getEmployeeMilestones,
  completeEmployeeMilestone,
} from "../services/api/employeeMilestones";

const BENCH_REASONS = [
  { value: "PROJECT_ENDED", label: "Project Ended" },
  { value: "PROJECT_DELAYED", label: "Project Delayed" },
  { value: "NEWLY_JOINED", label: "Newly Joined" },
  { value: "BETWEEN_PROJECTS", label: "Between Projects" },
  { value: "OTHER", label: "Other" },
];

// Moved here from candidate intake, 2026-07-23 -- Employment Type is a
// decision made at conversion time (when someone is actually hired),
// not something to ask a candidate before that. Maps to
// app.models.employee.EMPLOYMENT_TYPES; FIXED_TERM exists in that enum
// for other flows but isn't offered here since it's not one of the
// three options Avinash asked for.
const EMPLOYMENT_TYPES = [
  { value: "INTERN", label: "Intern" },
  { value: "PERMANENT", label: "Full Time" },
  { value: "CONTRACT", label: "Contract" },
];

function CreateEmployeeForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [title, setTitle] = useState("");
  const [skills, setSkills] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!firstName.trim() || !lastName.trim() || !email.trim() || !joiningDate) {
      setError("First name, last name, email, and joining date are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createEmployee({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        joining_date: joiningDate,
        current_title: title.trim() || undefined,
        current_skills: skills.trim()
          ? skills.split(",").map((s) => s.trim()).filter(Boolean)
          : undefined,
      });
      setFirstName("");
      setLastName("");
      setEmail("");
      setJoiningDate("");
      setTitle("");
      setSkills("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err.message || "Failed to create employee profile.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="primary" onClick={() => setOpen(true)}>
        <UserPlus className="h-4 w-4" /> New Employee Profile
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border p-4">
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="First name" value={firstName} onChange={setFirstName} />
        <Input label="Last name" value={lastName} onChange={setLastName} />
        <Input label="Email" value={email} onChange={setEmail} placeholder="name@blitzenx.com" />
        <Input label="Joining date" type="date" value={joiningDate} onChange={setJoiningDate} />
        <Input label="Current title" value={title} onChange={setTitle} placeholder="Guidewire Developer" />
        <Input label="Skills (comma-separated)" value={skills} onChange={setSkills} placeholder="Guidewire PolicyCenter, Java" />
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSubmit}>
          {saving ? "Saving…" : "Create Profile"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function ConvertCandidateForm({ onConverted }) {
  const [open, setOpen] = useState(false);
  const [candidateId, setCandidateId] = useState("");
  const [joiningDate, setJoiningDate] = useState("");
  const [title, setTitle] = useState("");
  const [employmentType, setEmploymentType] = useState("PERMANENT");
  // Added 2026-07-23: full street-level address is collected here, at
  // conversion time -- not during candidate intake, which only ever
  // captures city/state/country (see LocationCascadeSelect usage in
  // CandidateCreate.js / CandidateSelfService.js).
  const [fullAddress, setFullAddress] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!candidateId.trim() || !joiningDate) {
      setError("Candidate ID and joining date are both required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await convertCandidateToEmployee(candidateId.trim(), {
        joining_date: joiningDate,
        current_title: title.trim() || undefined,
        employment_type: employmentType,
        current_address: fullAddress.trim() || undefined,
        permanent_address: fullAddress.trim() || undefined,
      });
      setCandidateId("");
      setJoiningDate("");
      setTitle("");
      setEmploymentType("PERMANENT");
      setFullAddress("");
      setOpen(false);
      onConverted();
    } catch (err) {
      setError(err.message || "Failed to convert candidate to employee.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <ArrowRightLeft className="h-4 w-4" /> Convert Candidate to Employee
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border p-4">
      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-4">
        <Input label="Candidate ID" value={candidateId} onChange={setCandidateId} placeholder="candidate ID" />
        <Input label="Joining date" type="date" value={joiningDate} onChange={setJoiningDate} />
        <Input label="Current title" value={title} onChange={setTitle} placeholder="Guidewire Developer" />
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600">Employment Type</label>
          <select
            value={employmentType}
            onChange={(e) => setEmploymentType(e.target.value)}
            className="w-full rounded-lg border bg-white px-2 py-1.5 text-sm outline-none focus:border-gray-900"
          >
            {EMPLOYMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="mt-3">
        <TextArea
          label="Full Address"
          value={fullAddress}
          onChange={setFullAddress}
          rows={2}
          placeholder="Full street address, apartment/unit, postal code..."
        />
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSubmit}>
          {saving ? "Converting…" : "Convert"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function BulkImportForm({ onImported }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await bulkImportEmployees(file);
      setResult(res);
      onImported();
    } catch (err) {
      setError(err.message || "Bulk import failed.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={handleFileChange}
      />
      <Button variant="secondary" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
        <Upload className="h-4 w-4" /> {uploading ? "Importing…" : "Bulk Import (.xlsx)"}
      </Button>
      {error ? (
        <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}
      {result ? (
        <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <div className="font-semibold">
            {result.created} created, {result.skipped} skipped.
          </div>
          {result.errors?.length > 0 ? (
            <ul className="mt-1 list-disc pl-4 text-rose-700">
              {result.errors.map((e, i) => (
                <li key={i}>
                  Row {e.row}{e.email ? ` (${e.email})` : ""}: {e.reason}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="mt-1 text-[11px] text-gray-400">
        Header row: first_name, last_name, email, joining_date (YYYY-MM-DD) required; current_title, current_skills
        (comma-separated), employment_type, work_location, base_salary_usd_cents, billing_rate_usd_cents, nationality optional.
      </div>
    </div>
  );
}

function BenchActionCell({ employee, onChanged }) {
  const [reason, setReason] = useState("PROJECT_ENDED");
  const [busy, setBusy] = useState(false);

  const handleMark = async () => {
    setBusy(true);
    try {
      await markEmployeeOnBench(employee.id, reason);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    setBusy(true);
    try {
      await removeEmployeeFromBench(employee.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  if (employee.is_on_bench) {
    return (
      <Button variant="secondary" disabled={busy} onClick={handleRemove}>
        <LogIn className="h-4 w-4" /> Remove from Bench
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="rounded-lg border bg-white px-2 py-1.5 text-xs outline-none focus:border-gray-900"
      >
        {BENCH_REASONS.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <Button variant="secondary" disabled={busy} onClick={handleMark}>
        <LogOut className="h-4 w-4" /> Mark Bench
      </Button>
    </div>
  );
}

// S-351/HRMS-0512 -- read-only badges + engine history timeline.
// Deliberately no "set to CORE" control here: the source doc's own
// "Not In Scope" says do NOT build a UI bypass for engine assignment --
// CORE can only ever be set via the Core Eligibility Gate (HRMS-0513),
// once that approval workflow exists.
function EngineBadge({ employee }) {
  return (
    <div className="flex flex-col gap-1">
      <span
        className={cx(
          "inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
          employee.delivery_engine === "CORE"
            ? "border-purple-200 bg-purple-50 text-purple-800"
            : "border-blue-200 bg-blue-50 text-blue-800",
        )}
      >
        {employee.delivery_engine}
      </span>
      {employee.core_certified ? (
        <span className="inline-flex w-fit items-center gap-1 text-[11px] text-emerald-700">
          <Award className="h-3 w-3" /> Core Certified{employee.core_certified_date ? ` · ${employee.core_certified_date}` : ""}
        </span>
      ) : null}
    </div>
  );
}

function EngineHistoryPanel({ employeeId }) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState("");

  const handleToggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (history) return;
    try {
      const res = await getEngineHistory(employeeId);
      setHistory(res.history || []);
    } catch (err) {
      setError(err.message || "Failed to load engine history.");
    }
  };

  return (
    <div>
      <Button variant="ghost" onClick={handleToggle}>
        <History className="h-4 w-4" /> {open ? "Hide" : "View"} Engine History
      </Button>
      {open ? (
        <div className="mt-2 max-w-md rounded-lg border bg-gray-50 p-2 text-xs">
          {error ? <div className="text-rose-700">{error}</div> : null}
          {!history ? (
            <div className="text-gray-500">Loading…</div>
          ) : history.length === 0 ? (
            <div className="text-gray-500">No engine changes recorded.</div>
          ) : (
            <ul className="space-y-1">
              {history.map((h) => (
                <li key={h.id} className="border-b pb-1 last:border-b-0">
                  <span className="font-semibold text-gray-900">
                    {h.from_engine || "(new hire)"} → {h.to_engine}
                  </span>
                  <div className="text-gray-500">
                    {h.changed_at ? new Date(h.changed_at).toLocaleString() : "—"}
                    {h.changed_by ? ` · by ${h.changed_by}` : ""}
                    {h.approval_reference ? ` · Gate ${h.approval_reference}` : ""}
                  </div>
                  {h.reason ? <div className="text-gray-600">{h.reason}</div> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

// S-356/HRMS-0517 -- create a PERSONAL/ORG milestone for this employee.
// No PROJECT milestones here -- those are set on the project itself
// (Projects screen), per this story's own project_id/employee_id
// mutual-exclusivity rule.
function AddMilestoneForm({ employeeId, onAdded, onCancel }) {
  const [milestoneType, setMilestoneType] = useState("PERSONAL");
  const [title, setTitle] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim() || !targetDate) {
      setError("Title and target date are required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createEmployeeMilestone({
        milestone_type: milestoneType, title: title.trim(), target_date: targetDate, employee_id: employeeId,
      });
      onAdded();
    } catch (err) {
      setError(err.message || "Failed to create milestone.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 rounded-lg border bg-gray-50 p-2">
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="flex flex-wrap gap-2">
        <select
          value={milestoneType}
          onChange={(e) => setMilestoneType(e.target.value)}
          className="rounded-lg border bg-white px-2 py-1 text-xs outline-none"
        >
          <option value="PERSONAL">Personal</option>
          <option value="ORG">Org</option>
        </select>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Milestone title"
          className="rounded-lg border px-2 py-1 text-xs outline-none"
        />
        <input
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
          className="rounded-lg border px-2 py-1 text-xs outline-none"
        />
      </div>
      <div className="mt-2 flex gap-2">
        <Button variant="secondary" disabled={busy} onClick={handleSubmit}>
          Save
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

// S-354/HRMS-0515 (performance event timeline + score averages) +
// S-356/HRMS-0517 (personal/org milestones, completion auto-writes to
// the performance store above). Combined into one expandable panel
// since they're read together on an employee's profile per both docs'
// own UI Fields sketches.
function PerformanceMilestonesPanel({ employeeId }) {
  const [open, setOpen] = useState(false);
  const [performance, setPerformance] = useState(null);
  const [milestones, setMilestones] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const [perfRes, milestoneRes] = await Promise.all([
        getEmployeePerformance(employeeId),
        getEmployeeMilestones(employeeId),
      ]);
      setPerformance(perfRes);
      setMilestones(milestoneRes.milestones || []);
    } catch (err) {
      setError(err.message || "Failed to load performance/milestones.");
    }
  };

  const handleToggle = () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (!performance) load();
  };

  const handleComplete = async (milestoneId) => {
    try {
      await completeEmployeeMilestone(milestoneId);
      load();
    } catch (err) {
      setError(err.message || "Failed to complete milestone.");
    }
  };

  return (
    <div>
      <Button variant="ghost" onClick={handleToggle}>
        <LineChart className="h-4 w-4" /> {open ? "Hide" : "View"} Performance & Milestones
      </Button>
      {open ? (
        <div className="mt-2 max-w-lg rounded-lg border bg-gray-50 p-2 text-xs">
          {error ? <div className="mb-2 text-rose-700">{error}</div> : null}

          <div className="mb-2 flex items-center gap-1 font-semibold text-gray-700">
            <LineChart className="h-3 w-3" /> Performance (BU Head / RM / HR only)
          </div>
          {!performance ? (
            <div className="text-gray-500">Loading…</div>
          ) : (
            <>
              {Object.keys(performance.score_averages_by_event_type).length > 0 ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {Object.entries(performance.score_averages_by_event_type).map(([type, avg]) => (
                    <span key={type} className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-800">
                      {type}: {avg}
                    </span>
                  ))}
                </div>
              ) : null}
              {performance.events.length === 0 ? (
                <div className="mb-3 text-gray-500">No performance events recorded.</div>
              ) : (
                <ul className="mb-3 space-y-1">
                  {performance.events.slice(0, 10).map((e) => (
                    <li key={e.id} className="border-b pb-1 last:border-b-0">
                      <span className="font-semibold text-gray-900">{e.event_type}</span>
                      <span className="text-gray-500"> · {e.occurred_at ? new Date(e.occurred_at).toLocaleDateString() : "—"}</span>
                      {e.event_data ? <div className="text-gray-600">{JSON.stringify(e.event_data)}</div> : null}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-1 font-semibold text-gray-700">
              <Flag className="h-3 w-3" /> Milestones
            </div>
            <Button variant="ghost" onClick={() => setShowAddForm((v) => !v)}>
              {showAddForm ? "Cancel" : "Add"}
            </Button>
          </div>
          {showAddForm ? (
            <AddMilestoneForm employeeId={employeeId} onAdded={() => { setShowAddForm(false); load(); }} onCancel={() => setShowAddForm(false)} />
          ) : null}
          {!milestones ? (
            <div className="text-gray-500">Loading…</div>
          ) : milestones.length === 0 ? (
            <div className="text-gray-500">No milestones yet.</div>
          ) : (
            <ul className="space-y-1">
              {milestones.map((m) => (
                <li key={m.id} className="flex items-center justify-between rounded-lg border px-2 py-1">
                  <span>
                    [{m.milestone_type}] {m.title} · target {m.target_date}
                    {m.status === "COMPLETED" ? ` · completed ${m.completed_date}` : m.status === "OVERDUE" ? " · OVERDUE" : ""}
                  </span>
                  {m.status === "PENDING" || m.status === "IN_PROGRESS" ? (
                    <Button variant="ghost" onClick={() => handleComplete(m.id)}>
                      <CheckCircle2 className="h-3 w-3" /> Complete
                    </Button>
                  ) : (
                    <span className={m.status === "OVERDUE" ? "text-rose-700" : "text-emerald-700"}>{m.status}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function EmployeeDirectoryScreen() {
  const [employees, setEmployees] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [empRes, alertRes] = await Promise.all([getAllEmployees(), getBenchAgingAlerts()]);
      setEmployees(empRes?.employees || []);
      setAlerts(alertRes?.alerts || []);
    } catch (err) {
      setError(err.message || "Failed to load employees.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Employee Directory"
        subtitle="Create employee profiles and manage bench status. Every bench entry/exit is recorded in a permanent history for aging and cost reporting."
        icon={<UserPlus className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="flex flex-wrap items-start gap-2">
          <CreateEmployeeForm onCreated={load} />
          <ConvertCandidateForm onConverted={load} />
          <BulkImportForm onImported={load} />
        </div>

        {alerts.length > 0 ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-800">
              <AlertTriangle className="h-4 w-4" /> Bench aging alerts
            </div>
            <ul className="space-y-1 text-xs text-amber-800">
              {alerts.map((a) => (
                <li key={a.employee_id}>
                  {a.employee_name} has been on bench for {a.days_on_bench} days
                  {a.bench_cost_usd_cents != null
                    ? ` -- $${(a.bench_cost_usd_cents / 100).toFixed(2)} so far`
                    : ""}
                  .
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-4 overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Title / Skills</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Status</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Engine</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Bench</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                    Loading…
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                    No employees yet. Create one above.
                  </td>
                </tr>
              ) : (
                employees.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900">
                      <div className="font-semibold">
                        {e.first_name} {e.last_name}
                      </div>
                      <div className="text-xs text-gray-500">{e.email}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      <div>{e.current_title || "—"}</div>
                      <div>{(e.current_skills || []).join(", ") || "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">{e.status}</td>
                    <td className="px-4 py-3">
                      <EngineBadge employee={e} />
                      <div className="mt-1 flex flex-col items-start gap-1">
                        <EngineHistoryPanel employeeId={e.id} />
                        <PerformanceMilestonesPanel employeeId={e.id} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      {e.is_on_bench ? `On bench (${e.bench_days}d)` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <BenchActionCell employee={e} onChanged={load} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
