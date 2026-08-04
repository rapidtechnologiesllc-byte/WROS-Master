// S-434 -- org-wide Task Dashboard.
// Two-layer ranking (per Avinash's 2026-08-04 correction): everything
// due today or overdue is unconditionally on this list regardless of
// Priority (no blended score could bury a Low-priority due-today
// task); Priority only orders within that guaranteed set. Upcoming
// Urgent tasks (not due today) show separately, never mixed in.
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import {
  completeTask, confirmUrgentTask, createTask, getMyDayTasks, getUpcomingUrgentTasks,
} from "../services/api/tasks";

const PRIORITY_STYLES = {
  URGENT: "bg-red-100 text-red-800 border-red-300",
  HIGH: "bg-amber-100 text-amber-800 border-amber-300",
  MEDIUM: "bg-blue-50 text-blue-700 border-blue-200",
  LOW: "bg-gray-100 text-gray-600 border-gray-200",
};

function isOverdue(task, now) {
  return task.due_date && new Date(task.due_date) < now && task.status !== "COMPLETED";
}

function TaskRow({ task, now, onComplete, onConfirmUrgent }) {
  const overdue = isOverdue(task, now);
  return (
    <tr className="border-b border-gray-100 last:border-0">
      <td className="py-2 px-3 text-xs text-gray-500">#{task.id}</td>
      <td className="py-2 px-3">
        <div className="text-sm font-medium text-gray-900">{task.title}</div>
        {task.priority_challenged && (
          <div className="mt-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 inline-flex items-center gap-2">
            Thunder: {task.priority_challenge_note}
            <button
              className="underline font-medium"
              onClick={() => onConfirmUrgent(task.id)}
            >
              Confirm Urgent anyway
            </button>
          </div>
        )}
      </td>
      <td className="py-2 px-3">
        <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded border ${PRIORITY_STYLES[task.priority] || ""}`}>
          {task.priority}
        </span>
      </td>
      <td className={`py-2 px-3 text-sm ${overdue || task.is_escalated ? "text-red-600 font-semibold" : "text-gray-600"}`}>
        {task.due_date ? new Date(task.due_date).toLocaleString() : "--"}
        {task.is_escalated && <span className="ml-1 text-[10px] uppercase tracking-wide">escalated</span>}
      </td>
      <td className="py-2 px-3 text-xs text-gray-500">{task.department_id ?? "--"}</td>
      <td className="py-2 px-3 text-xs text-gray-500">{task.is_external ? "Yes" : "No"}</td>
      <td className="py-2 px-3">
        {task.status !== "COMPLETED" && (
          <button
            className="text-xs font-medium text-green-700 hover:underline"
            onClick={() => onComplete(task.id)}
          >
            Mark complete
          </button>
        )}
      </td>
    </tr>
  );
}

export default function MyTasksScreen() {
  const [tasks, setTasks] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", priority: "MEDIUM", due_date: "", is_external: false });
  const now = new Date();

  const load = async () => {
    try {
      const [daily, urgentUpcoming] = await Promise.all([getMyDayTasks(), getUpcomingUrgentTasks()]);
      setTasks(daily || []);
      setUpcoming(urgentUpcoming || []);
    } catch (err) {
      toast.error("Could not load your tasks.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleComplete = async (taskId) => {
    try {
      await completeTask(taskId);
      toast.success(`Task #${taskId} completed.`);
      load();
    } catch {
      toast.error("Could not complete task.");
    }
  };

  const handleConfirmUrgent = async (taskId) => {
    try {
      await confirmUrgentTask(taskId);
      toast.success("Urgent confirmed.");
      load();
    } catch {
      toast.error("Could not confirm.");
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    try {
      const created = await createTask({
        title: form.title,
        priority: form.priority,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        is_external: form.is_external,
      });
      if (created?.priority_challenged) {
        toast.warning(`Thunder: ${created.priority_challenge_note}`);
      } else {
        toast.success(`Task #${created.id} created.`);
      }
      setForm({ title: "", priority: "MEDIUM", due_date: "", is_external: false });
      setShowCreate(false);
      load();
    } catch {
      toast.error("Could not create task.");
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">My Tasks</h1>
          <p className="text-sm text-gray-500">Due today or overdue -- guaranteed on this list regardless of priority.</p>
        </div>
        <button
          className="bg-blue-600 text-white text-sm font-medium px-3 py-2 rounded hover:bg-blue-700"
          onClick={() => setShowCreate((s) => !s)}
        >
          + New Task
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
          <input
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            placeholder="Task title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div className="flex gap-3">
            <select
              className="border border-gray-300 rounded px-3 py-2 text-sm"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            >
              {["LOW", "MEDIUM", "HIGH", "URGENT"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <input
              type="datetime-local"
              className="border border-gray-300 rounded px-3 py-2 text-sm"
              value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            />
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={form.is_external}
                onChange={(e) => setForm({ ...form, is_external: e.target.checked })}
              />
              External stakeholder involved
            </label>
          </div>
          <button type="submit" className="bg-blue-600 text-white text-sm font-medium px-3 py-2 rounded hover:bg-blue-700">
            Create
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="border border-gray-200 rounded-lg overflow-hidden mb-6">
            <table className="w-full text-left">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="py-2 px-3">Task #</th>
                  <th className="py-2 px-3">Task</th>
                  <th className="py-2 px-3">Priority</th>
                  <th className="py-2 px-3">Due Date</th>
                  <th className="py-2 px-3">Department</th>
                  <th className="py-2 px-3">External</th>
                  <th className="py-2 px-3"></th>
                </tr>
              </thead>
              <tbody>
                {tasks.length === 0 ? (
                  <tr><td colSpan={7} className="py-6 text-center text-sm text-gray-400">Nothing due today. Nice.</td></tr>
                ) : (
                  tasks.map((t) => (
                    <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {upcoming.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Upcoming Urgent (heads-up, not due today)</h2>
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-left">
                  <tbody>
                    {upcoming.map((t) => (
                      <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
