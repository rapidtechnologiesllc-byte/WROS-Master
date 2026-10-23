// Log what was done on a task and the next action. The next action is
// created as a follow-up task (due on the chosen date, same candidate),
// and updates on a candidate's task also appear in that candidate's History.
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button, Input, Select, TextArea } from "./ui";
import { getTaskUpdateOptions, getTaskUpdates, logTaskUpdate } from "../services/api/tasks";
import TaskComments from "./TaskComments";

const EMPTY_FORM = {
  activity_type: "",
  outcome: "",
  notes: "",
  next_action_type: "",
  next_action_due: "",
  next_action_note: "",
  complete_task: false,
};

const labelFor = (options, value) => options.find((o) => o.value === value)?.label || value;

export default function TaskUpdateModal({ task, onClose, onSaved }) {
  const [options, setOptions] = useState({ activity_types: [], outcomes: [], next_action_types: [] });
  const [updates, setUpdates] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([getTaskUpdateOptions(), getTaskUpdates(task.id)])
      .then(([opts, list]) => {
        if (!active) return;
        setOptions(opts || { activity_types: [], outcomes: [], next_action_types: [] });
        setUpdates(list);
      })
      .catch((err) => active && setError(`Could not load task updates: ${err.message}`));
    return () => {
      active = false;
    };
  }, [task.id]);

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }));

  const handleSave = async (e) => {
    e.preventDefault();
    setError(null);
    if (!form.activity_type || !form.notes.trim()) {
      setError("Pick what you did and describe it.");
      return;
    }
    if (form.next_action_type && !form.next_action_due) {
      setError("Give the next action a date.");
      return;
    }
    setSaving(true);
    try {
      const saved = await logTaskUpdate(task.id, {
        activity_type: form.activity_type,
        outcome: form.outcome || null,
        notes: form.notes,
        next_action_type: form.next_action_type || null,
        next_action_due: form.next_action_due ? new Date(form.next_action_due).toISOString() : null,
        next_action_note: form.next_action_note || null,
        complete_task: form.complete_task,
      });
      onSaved(saved);
    } catch (err) {
      setError(err.message || "Could not save the update.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <div className="mt-10 w-full max-w-2xl rounded-bx-lg bg-white shadow-xl">
        <div className="flex items-start justify-between border-b border-bx-border px-5 py-4">
          <div>
            <div className="text-xs text-gray-500">Task #{task.id}</div>
            <h2 className="text-base font-semibold text-gray-900">{task.title}</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-4 px-5 py-4">
          {error && <div className="rounded-bx border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

          <div>
            <div className="mb-2 text-sm font-semibold text-gray-800">What was done</div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Select
                label="Activity"
                value={form.activity_type}
                onChange={set("activity_type")}
                options={[{ value: "", label: "Select..." }, ...options.activity_types]}
              />
              <Select
                label="Outcome"
                value={form.outcome}
                onChange={set("outcome")}
                options={[{ value: "", label: "Select..." }, ...options.outcomes]}
              />
            </div>
            <div className="mt-3">
              <TextArea label="Notes" value={form.notes} onChange={set("notes")} rows={3} placeholder="What happened, what you learned" />
            </div>
          </div>

          <div>
            <div className="mb-2 text-sm font-semibold text-gray-800">Next action</div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Select
                label="Type"
                value={form.next_action_type}
                onChange={set("next_action_type")}
                options={[{ value: "", label: "No next action" }, ...options.next_action_types]}
              />
              <Input
                label="Due"
                type="datetime-local"
                value={form.next_action_due}
                onChange={set("next_action_due")}
                disabled={!form.next_action_type}
              />
            </div>
            {form.next_action_type && (
              <div className="mt-3">
                <TextArea label="What needs to be done" value={form.next_action_note} onChange={set("next_action_note")} rows={2} />
              </div>
            )}
            {form.next_action_type && (
              <p className="mt-2 text-xs text-gray-500">This creates a follow-up task in your My Tasks on the due date.</p>
            )}
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={form.complete_task} onChange={(e) => set("complete_task")(e.target.checked)} />
            This update completes the task
          </label>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save update"}</Button>
          </div>
        </form>

        <div className="border-t border-bx-border px-5 py-4">
          <div className="mb-2 text-sm font-semibold text-gray-800">Previous updates</div>
          {updates.length === 0 ? (
            <p className="text-sm text-gray-400">No updates logged yet.</p>
          ) : (
            <ul className="space-y-3">
              {updates.map((u) => (
                <li key={u.id} className="rounded-bx border border-bx-border px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
                    <span>
                      <span className="font-semibold text-gray-800">{labelFor(options.activity_types, u.activity_type)}</span>
                      {u.outcome && ` -- ${labelFor(options.outcomes, u.outcome)}`}
                      {u.task_id !== task.id && ` (on task #${u.task_id})`}
                    </span>
                    <span>{u.created_by_name} · {u.created_at ? new Date(u.created_at).toLocaleString() : ""}</span>
                  </div>
                  <div className="mt-1 whitespace-pre-wrap text-gray-800">{u.notes}</div>
                  {u.next_action_type && (
                    <div className="mt-1 text-xs text-bx-orange">
                      Next: {labelFor(options.next_action_types, u.next_action_type)}
                      {u.next_action_due && ` by ${new Date(u.next_action_due).toLocaleString()}`}
                      {u.next_action_note && ` -- ${u.next_action_note}`}
                      {u.follow_up_task_id && ` (task #${u.follow_up_task_id})`}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <TaskComments taskId={task.id} />
      </div>
    </div>
  );
}
