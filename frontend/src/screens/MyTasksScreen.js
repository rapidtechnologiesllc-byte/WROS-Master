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
  approveTaskReplyDraft, completeTask, confirmUrgentTask, createTask, discardTaskReplyDraft, getMyDayTasks,
  getScheduledTasks, getTaskReplyDraft, getUpcomingUrgentTasks,
} from "../services/api/tasks";
import TaskUpdateModal from "../components/TaskUpdateModal";
import ExpenseReviewModal from "../components/ExpenseReviewModal";
import { SubmitFeedbackModal } from "./tabs/InterviewsTab";
import { getFeedbackForm, markCandidateNoShow, submitInterviewFeedback } from "../services/api/interviews";
import { ROUTES } from "../utils/Routes";
import { hasPermission } from "../utils/permissionsRoleTemplate";
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

// The task itself (CEO 2026-11-02: "click on the task shouldnt open candidate but the exact step or the
// task and what has to be done on it"): what is needed, who it is about, the email behind it and, when
// the system drafted an answer, that reply to approve (edit first if needed) or discard.
const SUBMIT_FEEDBACK = "SUBMIT_FEEDBACK";
const REVIEW_EXPENSE = "REVIEW_EXPENSE";
const OPEN_FINANCE = "OPEN_FINANCE";

// The same form as the candidate's Interviews tab; submitting it is what closes the task.
function TaskFeedbackModal({ task, onClose, onDone }) {
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let live = true;
    getFeedbackForm(task.interview_id)
      .then((data) => { if (live) setForm(data); })
      .catch((err) => { if (live) setNotice(err?.message || "Could not open this interview."); });
    return () => { live = false; };
  }, [task.interview_id]);

  const submit = async (values) => {
    try {
      setLoading(true);
      setNotice("");
      await submitInterviewFeedback({
        interviewId: task.interview_id,
        interviewerId: values.interviewerId,
        technicalScore: Number(values.technical_score),
        communicationScore: Number(values.communication_score),
        problemSolvingScore: Number(values.problem_solving_score),
        cultureFitScore: Number(values.culture_fit_score),
        comments: values.comments.trim(),
        recommendation: values.recommendation,
      });
      onDone("Feedback submitted. The task is closed.");
    } catch (err) {
      setNotice(err?.message || "Could not submit the feedback.");
      setLoading(false);
    }
  };

  const noShow = async () => {
    try {
      setLoading(true);
      setNotice("");
      await markCandidateNoShow(task.interview_id);
      onDone("Recorded. We emailed the candidate to reschedule and the task is closed.");
    } catch (err) {
      setNotice(err?.message || "Could not record that.");
      setLoading(false);
    }
  };

  if (!form && !notice) return null;
  return (
    <SubmitFeedbackModal
      interview={form || { id: task.interview_id }}
      panelMembers={form?.panel_members || []}
      loggedInInterviewerId={task.assigned_to_user_id}
      loading={loading}
      notice={notice}
      noticeType="error"
      onClose={onClose}
      onSubmit={submit}
      onNoShow={noShow}
    />
  );
}

function TaskPanel({ task, onClose, onNavigate, onComplete, onLogUpdate, onSubmitFeedback, onChanged }) {
  const [draft, setDraft] = useState(undefined);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  useEffect(() => {
    let cancelled = false;
    getTaskReplyDraft(task.id)
      .then((data) => { if (!cancelled) { setDraft(data); setText(data?.text || ""); } })
      .catch((err) => {
        console.error("[TaskPanel] Failed to load the drafted reply:", err);
        if (!cancelled) { setDraft(null); setError(`Could not load the drafted reply: ${err.message}`); }
      });
    return () => { cancelled = true; };
  }, [task.id]);

  const act = async (fn, message) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      setDone(message);
      setDraft(null);
      onChanged();
    } catch (err) {
      setError(err.message || "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <div className="text-xs text-gray-500">Task #{task.id} · {task.priority}{task.due_date ? ` · due ${new Date(task.due_date).toLocaleString()}` : ""}</div>
            <h2 className="text-base font-semibold text-gray-900">{task.title}</h2>
            {task.related_name ? (
              <div className="mt-1 text-sm text-gray-600">
                About {task.related_kind ? task.related_kind.toLowerCase() : ""}{" "}
                {task.related_link ? (
                  <button className="text-blue-600 hover:underline" onClick={() => onNavigate({ ...task, link: task.related_link })}>
                    {task.related_name}
                  </button>
                ) : task.related_name}
              </div>
            ) : null}
          </div>
          <button className="text-gray-400 hover:text-gray-700" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        {done ? <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{done}</div> : null}
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

        {draft ? (
          <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3">
            <div className="mb-1 text-xs font-semibold uppercase text-blue-800">
              Drafted reply · {draft.composed_by === "claude" ? "written by Claude" : "written from the job record"}
            </div>
            {draft.their_email ? (
              <div className="mb-2 rounded-lg bg-white p-2 text-xs text-gray-600 whitespace-pre-wrap">
                <span className="font-semibold text-gray-800">Their email: </span>{draft.their_email.slice(0, 1200)}
              </div>
            ) : null}
            <div className="mb-1 text-xs text-gray-600">Subject: {draft.subject}</div>
            <textarea
              className="h-48 w-full rounded-lg border border-gray-300 p-2 text-sm focus:border-bx-orange focus:outline-none"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={busy}
            />
            <div className="mt-1 text-[11px] text-gray-500">Greeting, your name and the opt-out line are added when it is sent.</div>
            <div className="mt-2 flex gap-2">
              <Button onClick={() => act(() => approveTaskReplyDraft(task.id, text), "Approved. Thunder sends it in the candidate's thread and closes this task.")} disabled={busy || !text.trim()}>
                {busy ? "Sending…" : "Approve and send"}
              </Button>
              <Button variant="ghost" onClick={() => act(() => discardTaskReplyDraft(task.id), "Draft discarded.")} disabled={busy}>Discard draft</Button>
            </div>
          </div>
        ) : draft === undefined ? (
          <div className="mb-4 text-sm text-gray-500">Loading…</div>
        ) : null}

        <div className="mb-1 text-xs font-semibold uppercase text-gray-500">What this is about</div>
        <div className="mb-4 whitespace-pre-wrap rounded-lg border bg-gray-50 p-3 text-sm text-gray-700">
          {task.description || "No details were recorded on this task."}
        </div>

        {task.status !== "COMPLETED" && task.system_action === SUBMIT_FEEDBACK ? (
          <Button variant="ghost" onClick={() => { onSubmitFeedback(task); onClose(); }}>Submit feedback</Button>
        ) : task.status !== "COMPLETED" ? (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onLogUpdate(task)}>Log update</Button>
            <Button variant="ghost" onClick={() => { onComplete(task.id); onClose(); }}>Mark complete</Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TaskRow({ task, now, onComplete, onConfirmUrgent, onNavigate, onLogUpdate, onSubmitFeedback, onOpen }) {
  const overdue = isOverdue(task, now);
  return (
    <tr className="border-b border-bx-border last:border-0">
      <td className="py-2 px-3 text-xs text-gray-500">#{task.id}</td>
      <td className="py-2 px-3">
        <button
          onClick={() => onOpen(task)}
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
      <td className="py-2 px-3 text-sm">
        {task.related_name ? (
          <div>
            {task.related_link ? (
              <button className="text-left text-blue-600 hover:underline" onClick={() => onNavigate({ ...task, link: task.related_link })}>
                {task.related_name}
              </button>
            ) : (
              <span className="text-gray-800">{task.related_name}</span>
            )}
            <div className="text-[11px] uppercase tracking-wide text-gray-400">{task.related_kind}</div>
          </div>
        ) : (
          <span className="text-xs text-gray-400">--</span>
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
        {task.status !== "COMPLETED" && task.system_action === SUBMIT_FEEDBACK && (
          <button className="text-xs font-semibold text-bx-orange hover:underline" onClick={() => onSubmitFeedback(task)}>
            Submit feedback
          </button>
        )}
        {task.status !== "COMPLETED" && task.system_action === OPEN_FINANCE && (
          <button className="text-xs font-semibold text-bx-orange hover:underline" onClick={() => onOpen(task)}>
            Open in Finance
          </button>
        )}
        {task.status !== "COMPLETED" && task.system_action === REVIEW_EXPENSE && (
          <button className="text-xs font-semibold text-bx-orange hover:underline" onClick={() => onOpen(task)}>
            Review expense
          </button>
        )}
        {task.status !== "COMPLETED" && !task.system_action && (
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
  const [feedbackTask, setFeedbackTask] = useState(null);
  const [openTask, setOpenTask] = useState(null);
  const [reviewTask, setReviewTask] = useState(null);
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

  // Task emails link here with ?task=<id> when the task has no record of its own: open that task
  useEffect(() => {
    const taskId = Number(searchParams.get("task"));
    if (!taskId || loading) return;
    const found = [...tasks, ...upcoming, ...scheduled].find((t) => t.id === taskId);
    if (found?.system_action === REVIEW_EXPENSE) setReviewTask(found);
    else if (found?.system_action === OPEN_FINANCE) navigate(found.link);
    else if (found) setUpdatingTask(found);
    else setActionError(`Task #${taskId} is not open on your list (it may be completed or assigned to someone else).`);
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams, loading, tasks, upcoming, scheduled, navigate]);

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

  // An expense task opens its review; any other task its panel
  const openOrReview = (task) => {
    if (task.system_action === REVIEW_EXPENSE) setReviewTask(task);
    else if (task.system_action === OPEN_FINANCE) navigate(task.link);
    else setOpenTask(task);
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
      navigate("/candidates?view=linkedin");
    } else {
      // No record behind it (e.g. a forwarded email): the task itself is the work -- open it
      setUpdatingTask(task);
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
          <p className="text-sm text-gray-500">Due today, overdue or with no due date -- guaranteed on this list regardless of priority.</p>
        </div>
        <div className="flex items-center gap-4">
          <OutlookConnection onError={setActionError} />
          {/* Hiring Manager Review opens from here, not the menu (CEO 2026-11-09) */}
          {hasPermission("candidate-review", "view") || hasPermission("rehire-approval", "view") ? (
            <Button variant="ghost" onClick={() => navigate("/hm-review")}>Hiring Manager Review</Button>
          ) : null}
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
                  <th className="py-2 px-3">Related to</th>
                  <th className="py-2 px-3">Priority</th>
                  <th className="py-2 px-3">Due Date</th>
                  <th className="py-2 px-3">Department</th>
                  <th className="py-2 px-3">External</th>
                  <th className="py-2 px-3"></th>
                </tr>
              </thead>
              <tbody>
                {tasks.length === 0 ? (
                  <tr><td colSpan={8} className="py-6 text-center text-sm text-gray-400">Nothing due today. Nice.</td></tr>
                ) : (
                  tasks.map((t) => (
                    <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} onSubmitFeedback={setFeedbackTask} onOpen={openOrReview} />
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
                      <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} onSubmitFeedback={setFeedbackTask} onOpen={openOrReview} />
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
                      <TaskRow key={t.id} task={t} now={now} onComplete={handleComplete} onConfirmUrgent={handleConfirmUrgent} onNavigate={handleNavigateTask} onLogUpdate={setUpdatingTask} onSubmitFeedback={setFeedbackTask} onOpen={openOrReview} />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {openTask && (
        <TaskPanel task={openTask} onClose={() => setOpenTask(null)} onNavigate={handleNavigateTask}
          onComplete={handleComplete} onLogUpdate={setUpdatingTask} onSubmitFeedback={setFeedbackTask} onChanged={load} />
      )}

      {reviewTask && (
        <ExpenseReviewModal expenseId={reviewTask.expense_id} onClose={() => setReviewTask(null)}
          onDone={(message) => { setReviewTask(null); setActionSuccess(message); load(); }} />
      )}

      {feedbackTask && (
        <TaskFeedbackModal task={feedbackTask} onClose={() => setFeedbackTask(null)}
          onDone={(message) => { setFeedbackTask(null); setActionSuccess(message); load(); }} />
      )}

      {updatingTask && (
        <TaskUpdateModal task={updatingTask} onClose={() => setUpdatingTask(null)} onSaved={handleUpdateSaved} />
      )}
    </div>
  );
}
