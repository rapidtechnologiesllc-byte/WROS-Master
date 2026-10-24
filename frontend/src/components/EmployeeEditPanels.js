// Employee drawer editing: details (name, email, title, work location) and employment changes
// (serving notice, exit, leave). The server decides what is allowed: the actions offered are the
// employee's employment_actions, and every refusal is shown, not hidden.
import { useEffect, useState } from "react";
import { Button, Input, Select } from "./ui";
import { confirmDialog } from "../utils/dialogs";
import {
  changeEmployeeEmployment,
  getEmployeeEditOptions,
  updateEmployeeDetails,
  updateEmployeeHtd,
} from "../services/api/employees";

const statusLabel = (value) => (value || "").replace(/_/g, " ").toLowerCase();

export function EmployeeDetailsForm({ employee, onSaved, onCancel }) {
  const [form, setForm] = useState({
    first_name: employee.first_name || "",
    last_name: employee.last_name || "",
    email: employee.email || "",
    current_title: employee.current_title || "",
    work_location: employee.work_location || "",
  });
  const [workLocations, setWorkLocations] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getEmployeeEditOptions()
      .then((options) => setWorkLocations(options.work_locations))
      .catch((err) => setError(`Could not load the form options: ${err.message}`));
  }, []);

  const set = (field) => (value) => setForm((current) => ({ ...current, [field]: value }));
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const changes = Object.fromEntries(Object.entries(form).filter(([key, value]) => value !== (employee[key] || "")));
      onSaved(Object.keys(changes).length ? await updateEmployeeDetails(employee.id, changes) : employee);
    } catch (err) {
      console.error("[EmployeeDetailsForm] Failed to save:", err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 rounded-xl border bg-gray-50 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="First name" value={form.first_name} onChange={set("first_name")} />
        <Input label="Last name" value={form.last_name} onChange={set("last_name")} />
        <div>
          <Input label="Email" value={form.email} onChange={set("email")} disabled={employee.has_login} />
          {employee.has_login ? (
            <div className="mt-1 text-xs text-gray-500">They sign in with this email: change it in Users &amp; Access.</div>
          ) : null}
        </div>
        <Input label="Title" value={form.current_title} onChange={set("current_title")} />
        <Select label="Work location" value={form.work_location} onChange={set("work_location")}
          options={workLocations.map((value) => ({ value, label: statusLabel(value) }))} />
      </div>
      {error ? <div className="text-sm text-rose-700">{error}</div> : null}
      <div className="flex gap-2">
        <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save details"}</Button>
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

// What each employment change asks for
const CHANGES = {
  START_NOTICE: { label: "Start notice period", date: "Last working day", button: "Start notice" },
  RECORD_EXIT: { label: "Record exit", date: "Exit date (last day worked)", button: "Record exit", danger: true },
  START_LEAVE: { label: "Start leave", button: "Start leave" },
  END_LEAVE: { label: "Back from leave", button: "Back from leave" },
};

export function EmploymentActions({ employee, onChanged }) {
  const [action, setAction] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const actions = (employee.employment_actions || []).filter((key) => CHANGES[key]);
  if (!actions.length) return null;

  const open = (key) => {
    setAction(key);
    setEffectiveDate("");
    setReason("");
    setError("");
  };
  const submit = async () => {
    const change = CHANGES[action];
    if (action === "RECORD_EXIT" && !(await confirmDialog(
      `Record ${employee.first_name}'s exit? Their allocations end on the exit date, they leave the bench `
      + "and their WROS login is closed. They move to Past Employees.",
    ))) return;
    setBusy(true);
    setError("");
    try {
      const updated = await changeEmployeeEmployment(employee.id, {
        action, reason, effective_date: change.date ? effectiveDate || null : null,
      });
      setAction("");
      onChanged(updated);
    } catch (err) {
      console.error("[EmploymentActions] Change refused:", err);
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {actions.map((key) => (
          <Button key={key} size="sm" variant={key === action ? "primary" : "secondary"} onClick={() => open(key)}>
            {CHANGES[key].label}
          </Button>
        ))}
      </div>
      {action && (
        <div className="space-y-3 rounded-xl border bg-gray-50 p-4">
          {CHANGES[action].date && (
            <Input label={CHANGES[action].date} type="date" value={effectiveDate} onChange={setEffectiveDate} />
          )}
          <Input label="Reason" value={reason} onChange={setReason} placeholder="Required" />
          {error ? <div className="text-sm text-rose-700">{error}</div> : null}
          <div className="flex gap-2">
            <Button onClick={submit} disabled={busy || !reason.trim()}
              className={CHANGES[action].danger ? "bg-rose-600 hover:bg-rose-700" : undefined}>
              {busy ? "Saving..." : CHANGES[action].button}
            </Button>
            <Button variant="secondary" onClick={() => setAction("")}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}

// Hire-Train-Deploy: on the track (phase) or not. Phases come from the server.
export function HtdControl({ employee, onChanged, canEdit }) {
  const [phases, setPhases] = useState([]);
  const [value, setValue] = useState(employee.htd_track ? employee.htd_phase || "" : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setValue(employee.htd_track ? employee.htd_phase || "" : "");
  }, [employee.htd_track, employee.htd_phase]);

  useEffect(() => {
    getEmployeeEditOptions()
      .then((options) => setPhases(options.htd_phases))
      .catch((err) => setError(`Could not load HTD phases: ${err.message}`));
  }, []);

  const save = async (next) => {
    setValue(next);
    setBusy(true);
    setError("");
    try {
      onChanged(await updateEmployeeHtd(employee.id, next ? { htd_track: true, htd_phase: next } : { htd_track: false }));
    } catch (err) {
      console.error("[HtdControl] Failed to save:", err);
      setError(err.message);
      setValue(employee.htd_track ? employee.htd_phase || "" : "");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <Select value={value} onChange={save} disabled={busy || !canEdit}
        options={[{ value: "", label: "Not in HTD" }, ...phases.map((phase) => ({ value: phase, label: statusLabel(phase) }))]} />
      {employee.htd_track && employee.htd_start_date ? (
        <div className="mt-1 text-xs text-gray-500">since {employee.htd_start_date}</div>
      ) : null}
      {error ? <div className="mt-1 text-xs text-rose-700">{error}</div> : null}
    </div>
  );
}
