// S-245 (Create Employee Profile) + S-246 (Mark Employee as Bench) +
// S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report).
import { useEffect, useState } from "react";
import { UserPlus, RefreshCw, AlertTriangle, LogOut, LogIn } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  createEmployee,
  getAllEmployees,
  getBenchAgingAlerts,
  markEmployeeOnBench,
  removeEmployeeFromBench,
} from "../services/api/employees";

const BENCH_REASONS = [
  { value: "PROJECT_ENDED", label: "Project Ended" },
  { value: "PROJECT_DELAYED", label: "Project Delayed" },
  { value: "NEWLY_JOINED", label: "Newly Joined" },
  { value: "BETWEEN_PROJECTS", label: "Between Projects" },
  { value: "OTHER", label: "Other" },
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

        <CreateEmployeeForm onCreated={load} />

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
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Bench</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                    Loading…
                  </td>
                </tr>
              ) : employees.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
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
