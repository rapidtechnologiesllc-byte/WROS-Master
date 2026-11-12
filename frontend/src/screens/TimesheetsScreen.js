// S-220 (Create Weekly Timesheet) + S-221 (Validation & Submission
// Lock) + S-222 (Manager Approval) -- the "time tracking" link in
// Avinash's stated MVP chain (candidate -> ... -> assign project ->
// time tracking -> resource management).
// CEO 2026-11-11: only the employee enters and submits their own week (is_own, enforced by the
// server); everyone else reviews. Each week shows its dates, where the time is logged (Staff Aug,
// project, bench work item) and where it stands: reporting manager -> Finance -> invoice. Bench
// time is logged against a work item a BU leader approved (accelerator, certification, other work).
import { useCallback, useEffect, useMemo, useState } from "react";
import { Clock, RefreshCw, Send, CheckCircle2, XCircle, RotateCcw, AlertTriangle, MessageSquareWarning } from "lucide-react";
import { Card, Button, Input, Select, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  createWeeklyDraft,
  upsertTimesheetEntries,
  submitTimesheet,
  approveTimesheet,
  rejectTimesheet,
  reopenTimesheet,
  getTimesheets,
  getTimesheetAllocations,
  scanTimesheetAnomalies,
  raiseTimesheetDispute,
  getTimesheetDisputes,
  resolveTimesheetDispute,
  getWorkItems,
  createWorkItem,
  closeWorkItem,
} from "../services/api/timesheets";
import { dayDate, dayName, todayIso, weekDays, weekRange, WORK_TYPE_STYLES } from "../utils/timesheetWeek";

const ANOMALY_LABELS = {
  WEEKEND: "Weekend hours",
  OVER_12H: "12+ hours in a day",
  COMPLETED_PROJECT: "Logged against a completed project",
  DUPLICATE: "Duplicate entry across allocations",
};

const DISPUTE_STATUS_STYLES = {
  OPEN: "border-purple-200 bg-purple-50 text-purple-800",
  UNDER_REVIEW: "border-purple-200 bg-purple-50 text-purple-800",
  RESOLVED_ADJUSTED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  RESOLVED_CONFIRMED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  CANCELLED: "border-gray-200 bg-gray-50 text-gray-700",
};

const OPEN_DISPUTE_STATUSES = ["OPEN", "UNDER_REVIEW"];

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// how the list is grouped: by where the time is logged
const GROUP_ORDER = ["STAFF_AUG", "PROJECT", "BENCH", "INTERNAL_TASK"];
const GROUP_TITLES = {
  STAFF_AUG: "Staff Aug (client placements)", PROJECT: "Project work", BENCH: "Bench work (accelerators, certifications, approved work)",
  INTERNAL_TASK: "Internal tasks",
};

const STATUS_STYLES = {
  DRAFT: "border-gray-200 bg-gray-50 text-gray-800",
  SUBMITTED: "border-amber-200 bg-amber-50 text-amber-800",
  APPROVED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  REJECTED: "border-rose-200 bg-rose-50 text-rose-800",
  DISPUTED: "border-purple-200 bg-purple-50 text-purple-800",
};

// local calendar date: toISOString() would shift to UTC and give the previous day east of UTC
function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function CreateTimesheetForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [people, setPeople] = useState(null);
  const [employeeId, setEmployeeId] = useState("");
  const [allocationId, setAllocationId] = useState("");
  const [weekStart, setWeekStart] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const openForm = async () => {
    setOpen(true);
    setError("");
    try {
      setPeople(await getTimesheetAllocations());
    } catch (err) {
      setPeople([]);
      setError(`Could not load allocations: ${err.message}`);
    }
  };

  const employee = (people || []).find((p) => p.employee_id === employeeId);
  const pickEmployee = (id) => {
    setEmployeeId(id);
    const chosen = (people || []).find((p) => p.employee_id === id);
    setAllocationId(chosen && chosen.allocations.length === 1 ? chosen.allocations[0].id : "");
  };

  const handleSubmit = async () => {
    if (!allocationId || !weekStart) {
      setError("Pick the employee, their allocation and the week-starting Monday.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createWeeklyDraft(allocationId, weekStart);
      setEmployeeId("");
      setAllocationId("");
      setWeekStart("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err.message || "Failed to create weekly draft.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="primary" onClick={openForm}>
        <Clock className="h-4 w-4" /> New weekly timesheet (mine)
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
      {people && people.length === 0 && !error ? (
        <div className="mb-3 text-xs text-gray-500">
          You have no active allocation. Everyone starts their own week (My Timesheet); time on the bench is
          logged there against a bench work item.
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <Select
          label="Employee"
          value={employeeId}
          onChange={pickEmployee}
          options={[{ value: "", label: people ? "Pick an employee" : "Loading…" },
            ...(people || []).map((p) => ({ value: p.employee_id, label: p.employee_name }))]}
        />
        <Select
          label="Allocation"
          value={allocationId}
          onChange={setAllocationId}
          options={[{ value: "", label: employee ? "Pick an allocation" : "Pick an employee first" },
            ...(employee ? employee.allocations : []).map((a) => ({
              value: a.id, label: `${a.client_name} · ${a.demand_job_title} (from ${a.start_date})`,
            }))]}
        />
        <Input label="Week starting (Monday)" type="date" value={weekStart} onChange={setWeekStart} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={saving} onClick={handleSubmit}>
          {saving ? "Creating…" : "Create Draft"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function DisputeResolveForm({ dispute, onResolved }) {
  const [resolution, setResolution] = useState("CONFIRMED");
  const [notes, setNotes] = useState("");
  const [adjustedHours, setAdjustedHours] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleResolve = async () => {
    if (resolution === "ADJUSTED" && adjustedHours === "") {
      setError("Adjusted hours is required when resolving as Adjusted.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await resolveTimesheetDispute(dispute.id, {
        resolution,
        resolution_notes: notes,
        adjusted_hours: resolution === "ADJUSTED" ? Number(adjustedHours) : undefined,
      });
      onResolved();
    } catch (err) {
      setError(err.message || "Failed to resolve dispute.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 rounded-lg border bg-gray-50 p-2">
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
          className="rounded-lg border bg-white px-2 py-1 text-xs outline-none"
        >
          <option value="CONFIRMED">Confirmed (no change)</option>
          <option value="ADJUSTED">Adjusted</option>
        </select>
        {resolution === "ADJUSTED" ? (
          <input
            type="number"
            min="0"
            max="24"
            placeholder="Adjusted hours"
            value={adjustedHours}
            onChange={(e) => setAdjustedHours(e.target.value)}
            className="w-28 rounded-lg border px-2 py-1 text-xs outline-none"
          />
        ) : null}
      </div>
      <TextArea value={notes} onChange={setNotes} placeholder="Resolution notes" rows={2} className="mt-2" />
      <Button variant="primary" disabled={busy} onClick={handleResolve} className="mt-2">
        {busy ? "Resolving…" : "Resolve Dispute"}
      </Button>
    </div>
  );
}

function DisputeRow({ dispute, onResolved }) {
  const [showResolve, setShowResolve] = useState(false);
  const isOpen = OPEN_DISPUTE_STATUSES.includes(dispute.status);

  return (
    <div className="rounded-lg border px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={cx("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold", DISPUTE_STATUS_STYLES[dispute.status])}>
          {dispute.status}
        </span>
        <span className="text-[11px] text-gray-500">
          Raised by {dispute.raised_by} · original {dispute.original_hours}h
          {dispute.disputed_hours != null ? ` · disputed to ${dispute.disputed_hours}h` : ""}
          {dispute.adjusted_hours != null ? ` · adjusted to ${dispute.adjusted_hours}h` : ""}
        </span>
      </div>
      <div className="mt-1 text-xs text-gray-700">{dispute.reason}</div>
      {dispute.resolution_notes ? (
        <div className="mt-1 text-xs text-gray-500">Resolution: {dispute.resolution_notes}</div>
      ) : null}
      {isOpen ? (
        <div className="mt-2">
          <Button variant="ghost" onClick={() => setShowResolve((v) => !v)}>
            {showResolve ? "Cancel" : "Resolve"}
          </Button>
          {showResolve ? <DisputeResolveForm dispute={dispute} onResolved={() => { setShowResolve(false); onResolved(); }} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function RaiseDisputeForm({ timesheetId, onRaised, onCancel }) {
  const [raisedBy, setRaisedBy] = useState("RM");
  const [reason, setReason] = useState("");
  const [disputedHours, setDisputedHours] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async () => {
    if (reason.trim().length < 50) {
      setError("Reason must be at least 50 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await raiseTimesheetDispute(timesheetId, {
        raised_by: raisedBy,
        reason: reason.trim(),
        disputed_hours: disputedHours === "" ? undefined : Number(disputedHours),
      });
      onRaised();
    } catch (err) {
      setError(err.message || "Failed to raise dispute.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 rounded-lg border bg-gray-50 p-2">
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={raisedBy}
          onChange={(e) => setRaisedBy(e.target.value)}
          className="rounded-lg border bg-white px-2 py-1 text-xs outline-none"
        >
          <option value="RM">Raised by RM</option>
          <option value="EMPLOYEE">Raised by Employee</option>
          <option value="CLIENT">Raised by Client</option>
        </select>
        <input
          type="number"
          min="0"
          max="24"
          placeholder="Disputed hours (optional)"
          value={disputedHours}
          onChange={(e) => setDisputedHours(e.target.value)}
          className="w-40 rounded-lg border px-2 py-1 text-xs outline-none"
        />
      </div>
      <TextArea value={reason} onChange={setReason} placeholder="Reason (50+ characters)" rows={2} className="mt-2" />
      <div className="mt-2 flex gap-2">
        <Button variant="primary" disabled={busy} onClick={handleSubmit}>
          {busy ? "Submitting…" : "Submit Dispute"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function TimesheetCard({ timesheet, onChanged }) {
  const [hours, setHours] = useState(() => {
    const byDate = {};
    (timesheet.entries || []).forEach((e) => {
      byDate[e.entry_date] = String(e.hours);
    });
    return DAY_LABELS.map((_, i) => byDate[addDays(timesheet.week_starting_date, i)] || "");
  });
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [anomalies, setAnomalies] = useState(null);
  const [disputes, setDisputes] = useState(null);
  const [showDisputeForm, setShowDisputeForm] = useState(false);

  const days = weekDays(timesheet.week_starting_date);
  const today = todayIso();
  // every day of the week, so a day cleared on the screen is cleared on the server too
  const typedEntries = () => hours.map((h, i) => ({ entry_date: days[i], hours: Number(h) || 0, entry_type: "BILLABLE" }))
    .filter((e, i) => e.hours > 0 || (timesheet.entries || []).some((saved) => saved.entry_date === days[i]));
  const typedTotal = hours.reduce((sum, h) => sum + (Number(h) || 0), 0);

  const handleSaveEntries = async () => {
    setBusy(true);
    setError("");
    try {
      await upsertTimesheetEntries(timesheet.id, typedEntries());
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to save entries.");
    } finally {
      setBusy(false);
    }
  };

  // Submit sends what is on the screen: the typed hours are saved first (it used to submit the
  // last saved hours, so a week typed but not saved was refused as "no logged hours")
  const handleSubmit = async () => {
    if (typedTotal <= 0) {
      setError("Enter the hours you worked before submitting.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await upsertTimesheetEntries(timesheet.id, typedEntries());
      await submitTimesheet(timesheet.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to submit timesheet.");
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    setBusy(true);
    setError("");
    try {
      await approveTimesheet(timesheet.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to approve.");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (rejectReason.trim().length < 20) {
      setError("Rejection reason must be at least 20 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await rejectTimesheet(timesheet.id, rejectReason.trim());
      setShowReject(false);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to reject.");
    } finally {
      setBusy(false);
    }
  };

  const handleReopen = async () => {
    setBusy(true);
    setError("");
    try {
      await reopenTimesheet(timesheet.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to reopen.");
    } finally {
      setBusy(false);
    }
  };

  const handleScanAnomalies = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await scanTimesheetAnomalies(timesheet.id);
      setAnomalies(res.flags || []);
    } catch (err) {
      setError(err.message || "Failed to scan anomalies.");
    } finally {
      setBusy(false);
    }
  };

  const loadDisputes = async () => {
    try {
      const res = await getTimesheetDisputes(timesheet.id);
      setDisputes(res.disputes || []);
    } catch (err) {
      setError(err.message || "Failed to load disputes.");
    }
  };

  // only the employee enters and submits their own week; everyone else reviews
  const editable = timesheet.status === "DRAFT" && timesheet.is_own;

  return (
    <div className="rounded-2xl border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-900">
            {timesheet.employee_name}{timesheet.is_own ? <span className="ml-2 text-xs font-normal text-gray-500">(you)</span> : null}
          </div>
          <div className="text-xs text-gray-500">Week of {weekRange(timesheet.week_starting_date)}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-700">
            <span className={cx("inline-flex rounded-full border px-2 py-0.5 font-semibold", WORK_TYPE_STYLES[timesheet.work_type])}>
              {timesheet.work_group || "Time"}
            </span>
            <span>{timesheet.work_label}</span>
          </div>
        </div>
        <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", STATUS_STYLES[timesheet.status])}>
          {timesheet.status}
        </span>
      </div>

      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-7 gap-2">
        {DAY_LABELS.map((label, i) => (
          <div key={label}>
            <div className="mb-1 text-center text-[11px] font-semibold text-gray-500">
              {dayName(days[i])}<div className="font-normal text-gray-500">{dayDate(days[i])}</div>
            </div>
            <input
              type="number"
              min="0"
              max="24"
              value={hours[i]}
              title={days[i] > today ? "This day has not happened yet: hours are logged once worked" : undefined}
              disabled={!editable || days[i] > today}
              onChange={(e) => {
                const next = [...hours];
                next[i] = e.target.value;
                setHours(next);
              }}
              className="w-full rounded-lg border px-2 py-1.5 text-center text-sm outline-none focus:border-gray-900 disabled:bg-gray-100"
            />
          </div>
        ))}
      </div>

      <div className="mt-2 text-xs text-gray-600">
        Total: {editable ? typedTotal : timesheet.total_hours}h
        {editable ? "" : ` (billable ${timesheet.billable_hours}h)`}
      </div>
      {timesheet.pipeline?.text ? (
        <div className="mt-1 text-xs text-gray-600">Where it stands: {timesheet.pipeline.text}</div>
      ) : null}
      {timesheet.status === "DRAFT" && !timesheet.is_own ? (
        <div className="mt-1 text-xs text-gray-500">
          Only {timesheet.employee_name} can enter and submit this week (My Timesheet).
        </div>
      ) : null}

      {timesheet.rejection_reason ? (
        <div className="mt-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          Rejected: {timesheet.rejection_reason}
        </div>
      ) : null}

      {anomalies && anomalies.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {anomalies.map((a) => (
            <span
              key={a.id}
              className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800"
            >
              <AlertTriangle className="h-3 w-3" /> {ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}
            </span>
          ))}
        </div>
      ) : anomalies && anomalies.length === 0 ? (
        <div className="mt-2 text-[11px] text-gray-500">No anomalies found.</div>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="ghost" disabled={busy} onClick={handleScanAnomalies}>
          <AlertTriangle className="h-4 w-4" /> Scan for Anomalies
        </Button>
        {timesheet.status === "APPROVED" ? (
          <Button variant="ghost" disabled={busy} onClick={loadDisputes}>
            <MessageSquareWarning className="h-4 w-4" /> {disputes ? "Refresh Disputes" : "View Disputes"}
          </Button>
        ) : null}
        {editable ? (
          <>
            <Button variant="secondary" disabled={busy} onClick={handleSaveEntries}>
              Save Entries
            </Button>
            <Button variant="primary" disabled={busy} onClick={handleSubmit}>
              <Send className="h-4 w-4" /> Submit
            </Button>
          </>
        ) : null}
        {timesheet.status === "SUBMITTED" && !timesheet.is_own ? (
          <>
            <Button variant="success" disabled={busy} onClick={handleApprove}>
              <CheckCircle2 className="h-4 w-4" /> Approve
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => setShowReject((v) => !v)}>
              <XCircle className="h-4 w-4" /> Reject
            </Button>
          </>
        ) : null}
        {timesheet.status === "REJECTED" && timesheet.is_own ? (
          <Button variant="secondary" disabled={busy} onClick={handleReopen}>
            <RotateCcw className="h-4 w-4" /> Reopen for Editing
          </Button>
        ) : null}
      </div>

      {showReject ? (
        <div className="mt-3">
          <TextArea value={rejectReason} onChange={setRejectReason} placeholder="Reason (20+ characters)" rows={2} />
          <Button variant="danger" disabled={busy} onClick={handleReject} className="mt-2">
            Confirm Reject
          </Button>
        </div>
      ) : null}

      {timesheet.status === "APPROVED" && disputes ? (
        <div className="mt-3 border-t pt-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs font-semibold text-gray-700">Disputes</div>
            <Button variant="ghost" onClick={() => setShowDisputeForm((v) => !v)}>
              {showDisputeForm ? "Cancel" : "Raise Dispute"}
            </Button>
          </div>
          {showDisputeForm ? (
            <RaiseDisputeForm
              timesheetId={timesheet.id}
              onCancel={() => setShowDisputeForm(false)}
              onRaised={() => {
                setShowDisputeForm(false);
                loadDisputes();
              }}
            />
          ) : null}
          <div className="mt-2 grid gap-2">
            {disputes.length === 0 ? (
              <div className="text-xs text-gray-500">No disputes raised.</div>
            ) : (
              disputes.map((d) => <DisputeRow key={d.id} dispute={d} onResolved={loadDisputes} />)
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

// Bench work items: what bench time is logged against. A BU leader adds one (adding it is the
// approval) and closes it when the work is done.
function WorkItemsPanel() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await getWorkItems());
    } catch (err) {
      setError(`Could not load the bench work items: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!name.trim() || !category) {
      setError("Give the work item a name and say what kind of work it is.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createWorkItem({ name: name.trim(), category });
      setName("");
      await load();
    } catch (err) {
      setError(err.message || "Could not add the work item.");
    } finally {
      setBusy(false);
    }
  };

  const close = async (id) => {
    setBusy(true);
    setError("");
    try {
      await closeWorkItem(id);
      await load();
    } catch (err) {
      setError(err.message || "Could not close the work item.");
    } finally {
      setBusy(false);
    }
  };

  const categories = Object.entries(data?.categories || {});
  const items = data?.work_items || [];
  return (
    <div className="rounded-2xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-gray-900">Bench work items ({items.length})</div>
          <div className="text-xs text-gray-500">
            People on the bench log their time against one of these: an accelerator, a certification or other work a BU head approved.
          </div>
        </div>
        <Button variant="ghost" onClick={() => setOpen((v) => !v)}>{open ? "Hide" : "Show"}</Button>
      </div>
      {error ? <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
      {open ? (
        <div className="mt-3 grid gap-2">
          {items.length === 0 ? (
            <div className="text-xs text-gray-500">None yet. Until a BU head adds one, bench time has nothing to be logged against.</div>
          ) : items.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm">
              <div>
                <span className={cx("mr-2 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold", WORK_TYPE_STYLES.BENCH)}>
                  {item.category_label}
                </span>
                {item.name}
                <span className="ml-2 text-xs text-gray-500">
                  {item.business_unit_name || "all business units"}
                  {item.approved_by_name ? ` · approved by ${item.approved_by_name}` : ""}
                </span>
              </div>
              {data.can_manage ? <Button variant="ghost" disabled={busy} onClick={() => close(item.id)}>Close</Button> : null}
            </div>
          ))}
          {data?.can_manage ? (
            <div className="mt-1 grid gap-2 sm:grid-cols-3">
              <Input label="New work item" value={name} onChange={setName} placeholder="e.g. Claims intake accelerator" />
              <Select label="Kind of work" value={category} onChange={setCategory}
                options={[{ value: "", label: "Select…" }, ...categories.map(([value, label]) => ({ value, label }))]} />
              <div className="flex items-end">
                <Button variant="primary" disabled={busy} onClick={add}>Add (approve)</Button>
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-500">A BU head adds work items.</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function TimesheetsScreen() {
  const [timesheets, setTimesheets] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getTimesheets(statusFilter ? { status: statusFilter } : {});
      setTimesheets(res?.timesheets || []);
    } catch (err) {
      setError(err.message || "Failed to load timesheets.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // grouped by where the time is logged: Staff Aug, project work, bench work, internal tasks
  const groups = useMemo(() => GROUP_ORDER
    .map((type) => ({ type, rows: timesheets.filter((t) => (t.work_type || "STAFF_AUG") === type) }))
    .filter((g) => g.rows.length), [timesheets]);

  return (
    <div className="grid gap-4">
      <Card
        title="Timesheets"
        subtitle="Each person enters and submits their own week. It goes to their reporting manager, then to Finance on the invoice. Approved timesheets are immutable."
        icon={<Clock className="h-4 w-4" />}
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

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <CreateTimesheetForm onCreated={load} />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        <div className="mb-4"><WorkItemsPanel /></div>

        <div className="grid gap-3">
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : timesheets.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">No timesheets yet.</div>
          ) : (
            groups.map((group) => (
              <div key={group.type} className="grid gap-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  {GROUP_TITLES[group.type]} · {group.rows.length}
                </div>
                {group.rows.map((t) => <TimesheetCard key={`${t.id}-${t.status}-${t.total_hours}`} timesheet={t} onChanged={load} />)}
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
