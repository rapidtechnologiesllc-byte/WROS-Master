// Tasks about one candidate (Tasks tab): who does what by when, including repeating
// keep-in-touch tasks; completing a repeating one opens the next (task_service.complete_task).
import { useCallback, useEffect, useState } from "react";
import { Plus, Repeat } from "lucide-react";
import { Button, Input, Select, TextArea } from "./ui";
import { completeTask, createTask, getCandidateTasks, getTaskOptions, stopRepeatingTask } from "../services/api/tasks";
import { searchUsers } from "../services/api/users";

const EMPTY_FORM = { title: "", description: "", due_date: "", assigned_to_user_id: "", priority: "MEDIUM", recurrence: "" };
const FINISHED = ["COMPLETED", "CANCELLED"];

function label(value) {
  return value ? value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, " ") : "";
}

function formatDate(value) {
  return value ? new Date(value).toLocaleDateString() : "no date";
}

export default function CandidateTasks({ candidateId }) {
  const [tasks, setTasks] = useState([]);
  const [options, setOptions] = useState({ priorities: [], recurrences: [] });
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setTasks((await getCandidateTasks(candidateId)) || []);
  }, [candidateId]);

  useEffect(() => {
    if (!candidateId) return;
    load().catch((err) => setError(err.message || "Failed to load tasks."));
  }, [candidateId, load]);

  const openForm = async () => {
    setError("");
    try {
      const [opts, people] = await Promise.all([getTaskOptions(), searchUsers({ limit: 200 })]);
      setOptions(opts || { priorities: [], recurrences: [] });
      setUsers(Array.isArray(people?.users) ? people.users : []);
      setForm(EMPTY_FORM);
    } catch (err) {
      setError(err.message || "Failed to open the task form.");
    }
  };

  const run = async (action) => {
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
      return true;
    } catch (err) {
      setError(err.message || "Failed to update the task.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!form.title.trim()) return setError("Say what needs to be done.");
    if (!form.due_date) return setError("Pick a due date.");
    const created = await run(() => createTask({
      title: form.title.trim(),
      description: form.description.trim() || null,
      due_date: `${form.due_date}T09:00:00`,
      assigned_to_user_id: form.assigned_to_user_id || null, // empty = the creator
      priority: form.priority,
      recurrence: form.recurrence || null,
      candidate_id: candidateId,
    }));
    if (created) setForm(null);
  };

  const open = tasks.filter((t) => !FINISHED.includes(t.status));
  const done = tasks.filter((t) => FINISHED.includes(t.status));

  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="font-semibold text-gray-900">Tasks</div>
          <div className="text-xs text-gray-500">Follow-ups for this candidate. A repeating task continues until they join.</div>
        </div>
        {!form && (
          <Button onClick={openForm}>
            <Plus className="h-4 w-4" />New task
          </Button>
        )}
      </div>

      {error && <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      {form && (
        <div className="mb-4 grid gap-3 rounded-xl border bg-gray-50 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Input label="What needs to be done" value={form.title} placeholder="e.g. Monthly check-in call"
                   onChange={(v) => setForm({ ...form, title: v })} />
          </div>
          <div className="sm:col-span-2">
            <TextArea label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
          </div>
          <Input label="Due date" type="date" value={form.due_date} onChange={(v) => setForm({ ...form, due_date: v })} />
          <Select label="Assigned to" value={form.assigned_to_user_id}
                  onChange={(v) => setForm({ ...form, assigned_to_user_id: v })}
                  options={[{ value: "", label: "Me" },
                    ...users.map((u) => ({ value: u.user_id, label: `${u.user_name || u.user_email} (${u.user_email})` }))]} />
          <Select label="Priority" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })}
                  options={options.priorities} />
          <Select label="Repeat" value={form.recurrence} onChange={(v) => setForm({ ...form, recurrence: v })}
                  options={[{ value: "", label: "Does not repeat" }, ...options.recurrences]} />
          <div className="flex gap-2 sm:col-span-2">
            <Button onClick={save} disabled={busy}>{busy ? "Saving..." : "Create task"}</Button>
            <Button variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancel</Button>
          </div>
        </div>
      )}

      {open.length === 0 && !form && <div className="py-4 text-center text-sm text-gray-400">No open tasks.</div>}
      <div className="grid gap-2">
        {open.map((task) => (
          <div key={task.id} className="flex items-start justify-between gap-3 rounded-xl border px-4 py-3">
            <div>
              <div className="text-sm font-medium text-gray-900">
                {task.title}
                {task.recurrence && (
                  <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
                    <Repeat className="h-3 w-3" />{label(task.recurrence)}
                  </span>
                )}
              </div>
              {task.description && <div className="mt-1 whitespace-pre-line text-xs text-gray-500">{task.description}</div>}
              <div className="mt-1 text-xs text-gray-400">
                Due {formatDate(task.due_date)} · {task.assigned_to_name || "Unassigned"} · {label(task.priority)}
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              {task.recurrence && (
                <Button variant="ghost" disabled={busy} onClick={() => run(() => stopRepeatingTask(task.id))}>
                  Stop repeating
                </Button>
              )}
              <Button variant="secondary" disabled={busy} onClick={() => run(() => completeTask(task.id))}>
                Complete
              </Button>
            </div>
          </div>
        ))}
      </div>
      {done.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-semibold text-gray-500">Done ({done.length})</summary>
          <div className="mt-2 grid gap-1">
            {done.map((task) => (
              <div key={task.id} className="text-xs text-gray-500">
                {task.title} · {label(task.status)} {formatDate(task.completed_at)}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
