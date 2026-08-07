// S-434 -- org-wide Task Dashboard.
// Two-layer ranking (per Avinash's 2026-08-04 correction): everything
// due today or overdue is unconditionally on this list regardless of
// Priority (no blended score could bury a Low-priority due-today
// task); Priority only orders within that guaranteed set. Upcoming
// Urgent tasks (not due today) show separately, never mixed in.
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Card, Button, Input, Select } from "../components/ui";
import {
  completeTask, confirmUrgentTask, createTask, getMyDayTasks, getUpcomingUrgentTasks,
} from "../services/api/tasks";
import { createTicket, getTicketCategories } from "../services/api/tickets";

const TICKET_IMPACTS = ["INDIVIDUAL", "DEPARTMENT", "MULTIPLE_DEPARTMENTS", "ORG_WIDE"];
const TICKET_URGENCIES = ["LOW", "MODERATE", "CRITICAL"];
const TASK_PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];

const PRIORITY_STYLES = {
  URGENT: "bg-red-100 text-red-800 border-red-300",
  HIGH: "bg-amber-100 text-amber-800 border-amber-300",
  MEDIUM: "bg-bx-orange/10 text-bx-orange border-bx-orange/30",
  LOW: "bg-gray-100 text-gray-600 border-gray-200",
};

function isOverdue(task, now) {
  return task.due_date && new Date(task.due_date) < now && task.status !== "COMPLETED";
}

function TaskRow({ task, now, onComplete, onConfirmUrgent }) {
  const overdue = isOverdue(task, now);
  return (
    <tr className="border-b border-bx-border last:border-0">
      <td className="py-2 px-3 text-xs text-gray-500">#{task.id}</td>
      <td className="py-2 px-3">
        <div className="text-sm font-medium text-bx-slate">{task.title}</div>
        {task.priority_challenged && (
          <div className="mt-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-bx px-2 py-1 inline-flex items-center gap-2">
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
        <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-bx border ${PRIORITY_STYLES[task.priority] || ""}`}>
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
            className="text-xs font-semibold text-emerald-700 hover:underline"
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
  const [mode, setMode] = useState("TASK"); // TASK | TICKET
  const [form, setForm] = useState({ title: "", priority: "MEDIUM", due_date: "", is_external: false });
  const [ticketForm, setTicketForm] = useState({
    title: "", description: "", impact: "INDIVIDUAL", urgency: "MODERATE", category: "", is_external: false,
  });
  const [categories, setCategories] = useState([]);
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
    getTicketCategories().then(setCategories).catch(() => setCategories([]));
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

  const handleCreateTicket = async (e) => {
    e.preventDefault();
    if (!ticketForm.title.trim() || !ticketForm.category) return;
    try {
      const created = await createTicket(ticketForm);
      toast.success(`Ticket #${created.id} created -- routed to ${created.department_id ? `department ${created.department_id}` : "unassigned (no route configured for this category yet)"}.`);
      setTicketForm({ title: "", description: "", impact: "INDIVIDUAL", urgency: "MODERATE", category: "", is_external: false });
      setShowCreate(false);
      load();
    } catch {
      toast.error("Could not create ticket.");
    }
  };

  const categoryOptions = [
    { value: "", label: "Select category..." },
    ...categories.map((c) => ({ value: c.category, label: c.category })),
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm text-gray-500">Due today or overdue -- guaranteed on this list regardless of priority.</p>
        </div>
        <Button onClick={() => setShowCreate((s) => !s)}>+ New Task</Button>
      </div>

      {showCreate && (
        <Card bodyClassName="px-5 py-5" title={mode === "TASK" ? "New Task" : "New Help Desk Ticket"}>
          <div className="mb-4 flex gap-2 text-xs font-semibold">
            <button
              type="button"
              className={`px-3 py-1.5 rounded-full border transition ${mode === "TASK" ? "bg-bx-orange text-white border-bx-orange" : "bg-white text-gray-600 border-bx-border hover:bg-bx-light"}`}
              onClick={() => setMode("TASK")}
            >
              Task
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 rounded-full border transition ${mode === "TICKET" ? "bg-bx-orange text-white border-bx-orange" : "bg-white text-gray-600 border-bx-border hover:bg-bx-light"}`}
              onClick={() => setMode("TICKET")}
            >
              Help Desk Ticket
            </button>
          </div>

          {mode === "TASK" ? (
            <form onSubmit={handleCreate} className="space-y-3">
              <Input label="Task title" value={form.title} onChange={(v) => setForm({ ...form, title: v })} />
              <div className="flex flex-wrap gap-3">
                <Select label="Priority" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })} options={TASK_PRIORITIES} />
                <Input label="Due date" type="datetime-local" value={form.due_date} onChange={(v) => setForm({ ...form, due_date: v })} />
                <label className="flex items-center gap-2 text-sm text-gray-600 self-end pb-2.5">
                  <input
                    type="checkbox"
                    checked={form.is_external}
                    onChange={(e) => setForm({ ...form, is_external: e.target.checked })}
                  />
                  External stakeholder involved
                </label>
              </div>
              <Button type="submit">Create</Button>
            </form>
          ) : (
            <form onSubmit={handleCreateTicket} className="space-y-3">
              <Input label="What's the issue?" value={ticketForm.title} onChange={(v) => setTicketForm({ ...ticketForm, title: v })} />
              <label className="block">
                <div className="mb-1 text-xs font-semibold text-gray-700">Description (optional)</div>
                <textarea
                  className="w-full rounded-xl border border-bx-border bg-white px-3 py-2 text-sm outline-none focus:border-bx-orange"
                  rows={2}
                  value={ticketForm.description}
                  onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })}
                />
              </label>
              <div className="flex flex-wrap gap-3">
                <Select label="Category" value={ticketForm.category} onChange={(v) => setTicketForm({ ...ticketForm, category: v })} options={categoryOptions} />
                <Select
                  label="Impact"
                  value={ticketForm.impact}
                  onChange={(v) => setTicketForm({ ...ticketForm, impact: v })}
                  options={TICKET_IMPACTS.map((v) => ({ value: v, label: v.replace(/_/g, " ") }))}
                />
                <Select label="Urgency" value={ticketForm.urgency} onChange={(v) => setTicketForm({ ...ticketForm, urgency: v })} options={TICKET_URGENCIES} />
              </div>
              <p className="text-xs text-gray-500">Priority is derived from Impact + Urgency, not picked directly.</p>
              <Button type="submit">Submit Ticket</Button>
            </form>
          )}
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="border border-bx-border rounded-bx-lg overflow-hidden mb-6 bg-white shadow-sm">
            <table className="w-full text-left">
              <thead className="bg-bx-light text-xs uppercase text-gray-500">
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
              <div className="border border-bx-border rounded-bx-lg overflow-hidden bg-white shadow-sm">
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
