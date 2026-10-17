// S-434 -- org-wide Task Dashboard.
// Two-layer ranking (per Avinash's 2026-08-04 correction): everything
// due today or overdue is unconditionally on this list regardless of
// Priority (no blended score could bury a Low-priority due-today
// task); Priority only orders within that guaranteed set. Upcoming
// Urgent tasks (not due today) show separately, never mixed in.
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, CheckCircle, X } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import {
  completeTask, confirmUrgentTask, createTask, getMyDayTasks, getScheduledTasks, getUpcomingUrgentTasks,
} from "../services/api/tasks";
import TaskUpdateModal from "../components/TaskUpdateModal";
import { ROUTES } from "../utils/Routes";
import { connectOutlook, disconnectOutlook, getOutlookStatus } from "../services/api/msgraph";
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

function TaskRow({ task, now, onComplete, onConfirmUrgent, onNavigate, onLogUpdate }) {
  const overdue = isOverdue(task, now);
  return (
    <tr className="border-b border-bx-border last:border-0">
      <td className="py-2 px-3 text-xs text-gray-500">#{task.id}</td>
      <td className="py-2 px-3">
        <button
          onClick={() => onNavigate(task)}
          className="text-sm font-medium text-blue-600 hover:underline cursor-pointer text-left"
        >
          {task.title}
        </button>
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
      <td className="py-2 px-3 whitespace-nowrap">
        {task.status !== "COMPLETED" && (
          <div className="flex flex-col items-start gap-1">
            <button
              className="text-xs font-semibold text-bx-orange hover:underline"
              onClick={() => onLogUpdate(task)}
            >
              Log update
            </button>
            <button
              className="text-xs font-semibold text-emerald-700 hover:underline"
              onClick={() => onComplete(task.id)}
            >
              Mark complete
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

// Outlook mail capture: emails with known candidates/employees are logged
// to their History (subject, direction, time, link -- never the body).
function OutlookConnection({ onError }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => getOutlookStatus().then(setStatus).catch(() => setStatus({ linked: false }));
  useEffect(() => {
    refresh();
  }, []);

  const connect = async () => {
    setBusy(true);
    try {
      await connectOutlook();
    } catch (err) {
      onError(err.message || "Could not start the Microsoft sign-in.");
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await disconnectOutlook();
      await refresh();
    } catch (err) {
      onError(err.message || "Could not disconnect Outlook.");
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;
  if (!status.linked) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-600">
        {status.last_error && <span className="text-amber-700">{status.last_error}</span>}
        <Button variant="secondary" onClick={connect} disabled={busy}>Connect Outlook</Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-end text-xs text-gray-600">
      <span>
        Outlook: <span className="font-semibold text-gray-800">{status.account_email || "connected"}</span>
        {status.last_synced_at && ` · last sync ${new Date(status.last_synced_at).toLocaleString()}`}
        <button className="ml-2 underline hover:text-gray-900" onClick={disconnect} disabled={busy}>Disconnect</button>
      </span>
      {status.mail_access === false && status.last_error && (
        <span className="mt-1 text-amber-700">{status.last_error}</span>
      )}
    </div>
  );
}

export default function MyTasksScreen() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasks, setTasks] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [scheduled, setScheduled] = useState([]);
  const [updatingTask, setUpdatingTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [mode, setMode] = useState("TASK"); // TASK | TICKET
  const [form, setForm] = useState({ title: "", priority: "MEDIUM", due_date: "", is_external: false });
  const [ticketForm, setTicketForm] = useState({
    title: "", description: "", impact: "INDIVIDUAL", urgency: "MODERATE", category: "", is_external: false,
  });
  const [categories, setCategories] = useState([]);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const now = new Date();

  const load = async () => {
    try {
      const [daily, urgentUpcoming, followUps] = await Promise.all([
        getMyDayTasks(), getUpcomingUrgentTasks(), getScheduledTasks(),
      ]);
      setTasks(daily || []);
      setUpcoming(urgentUpcoming || []);
      setScheduled(followUps || []);
    } catch (err) {
      console.error("Could not load your tasks:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const outlook = searchParams.get("outlook");
    if (outlook === "connected") {
      setActionSuccess("Outlook connected. Emails with candidates and employees will appear on their History within 15 minutes.");
    } else if (outlook === "error") {
      setActionError(`Outlook was not connected: ${searchParams.get("reason") || "Microsoft sign-in failed"}`);
    }
    if (outlook) setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    load();
    getTicketCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const handleComplete = async (taskId) => {
    try {
      await completeTask(taskId);
      setActionSuccess(`Task #${taskId} completed.`);
      load();
    } catch {
      setActionError("Could not complete task.");
    }
  };

  const handleConfirmUrgent = async (taskId) => {
    try {
      await confirmUrgentTask(taskId);
      setActionSuccess("Urgent confirmed.");
      load();
    } catch {
      setActionError("Could not confirm.");
    }
  };

  const handleUpdateSaved = (saved) => {
    setUpdatingTask(null);
    setActionSuccess(
      saved?.follow_up_task_id
        ? `Update saved. Next action added as task #${saved.follow_up_task_id}.`
        : "Update saved."
    );
    load();
  };

  const handleNavigateTask = (task) => {
    // The task's own deep link wins (an in-app path set by whoever raised the task).
    if (task.link) {
      navigate(task.link);
      return;
    }
    // Tasks raised before links existed: open the record the task is linked to; the title is
    // only a fallback hint.
    const title = task.title || "";
    const isInterviewTask = Boolean(task.interview_id) || title.includes("Submit feedback") || title.includes("Interview");
    if (isInterviewTask && task.candidate_id) {
      // Interviews (schedule, panel, feedback) live on the candidate's Interview tab
      navigate(`/candidates/${task.candidate_id}?tab=interview`);
    } else if (title.includes("Submit Offer")) {
      navigate(ROUTES.OFFERS_LISTING);
    } else if (title.includes("Timesheet")) {
      navigate("/my-timesheet");
    } else if (task.candidate_id) {
      // Profile has the notes, history trail and stage bar for this candidate
      navigate(`/candidates/${task.candidate_id}`);
    } else if (title.includes("Review candidate") || isInterviewTask) {
      navigate("/candidates");
    } else if (title.startsWith("LinkedIn:")) {
      // Candidate record not created yet: work the item in the pipeline
      navigate("/linkedin-pipeline");
    } else {
      setActionError("No action configured for this task type.");
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
        setActionError(`Thunder: ${created.priority_challenge_note}`);
      } else {
        setActionSuccess(`Task #${created.id} created.`);
      }
      setForm({ title: "", priority: "MEDIUM", due_date: "", is_external: false });
      setShowCreate(false);
      load();
    } catch {
      setActionError("Could not create task.");
    }
  };

  const handleCreateTicket = async (e) => {
    e.preventDefault();
    if (!ticketForm.title.trim() || !ticketForm.category) return;
    try {
      const created = await createTicket(ticketForm);
      setActionSuccess(`Ticket #${created.id} created -- routed to ${created.department_id ? `department ${created.department_id}` : "unassigned (no route configured for this category yet)"}.`);
      setTicketForm({ title: "", description: "", impact: "INDIVIDUAL", urgency: "MODERATE", category: "", is_external: false });
      setShowCreate(false);
      load();
    } catch {
      setActionError("Could not create ticket.");
    }
  };

  const categoryOptions = [
    { value: "", label: "Select category..." },
    ...categories.map((c) => ({ value: c.category, label: c.category })),
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Action Error Banner */}
      {actionError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 text-sm font-medium">{actionError}</p>
            </div>
            <button
              onClick={() => setActionError(null)}
              className="text-red-600 hover:text-red-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Action Success Banner */}
      {actionSuccess && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-green-700 text-sm font-medium">{actionSuccess}</p>
            </div>
            <button
              onClick={() => setActionSuccess(null)}
              className="text-green-600 hover:text-green-800 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-sm text-gray-500">Due today or overdue -- guaranteed on this list regardless of priority.</p>
        </div>
        <div className="flex items-center gap-4">
          <OutlookConnection onError={setActionError} />
          <Button onClick={() => setShowCreate((s) => !s)}>+ New Task</Button>
        </div>
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
                    <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {scheduled.length > 0 && (
            <div className="mb-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Scheduled follow-ups (next 30 days)</h2>
              <div className="border border-bx-border rounded-bx-lg overflow-hidden bg-white shadow-sm">
                <table className="w-full text-left">
                  <tbody>
                    {scheduled.map((t) => (
                      <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {upcoming.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Upcoming Urgent (heads-up, not due today)</h2>
              <div className="border border-bx-border rounded-bx-lg overflow-hidden bg-white shadow-sm">
                <table className="w-full text-left">
                  <tbody>
                    {upcoming.map((t) => (
                      <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {updatingTask && (
        <TaskUpdateModal task={updatingTask} onClose={() => setUpdatingTask(null)} onSaved={handleUpdateSaved} />
      )}
    </div>
  );
}
