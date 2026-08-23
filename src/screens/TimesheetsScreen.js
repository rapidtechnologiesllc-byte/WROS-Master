// S-220 (Create Weekly Timesheet) + S-221 (Validation & Submission
// Lock) + S-222 (Manager Approval) -- the "time tracking" link in
// Avinash's stated MVP chain (candidate -> ... -> assign project ->
// time tracking -> resource management).
import { useEffect, useState } from "react";
import { Clock, RefreshCw, Send, CheckCircle2, XCircle, RotateCcw, AlertTriangle, MessageSquareWarning } from "lucide-react";
import { Card, Button, Input, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  createWeeklyDraft,
  upsertTimesheetEntries,
  submitTimesheet,
  approveTimesheet,
  rejectTimesheet,
  reopenTimesheet,
  getTimesheets,
  scanTimesheetAnomalies,
  getTimesheetAnomalies,
  raiseTimesheetDispute,
  getTimesheetDisputes,
  resolveTimesheetDispute,
} from "../services/api/timesheets";

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

const STATUS_STYLES = {
  DRAFT: "border-gray-200 bg-gray-50 text-gray-800",
  SUBMITTED: "border-amber-200 bg-amber-50 text-amber-800",
  APPROVED: "border-emerald-200 bg-emerald-50 text-emerald-800",
  REJECTED: "border-rose-200 bg-rose-50 text-rose-800",
  DISPUTED: "border-purple-200 bg-purple-50 text-purple-800",
};

function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function CreateTimesheetForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [allocationId, setAllocationId] = useState("");
  const [weekStart, setWeekStart] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!allocationId.trim() || !weekStart) {
      setError("Allocation ID and week-starting Monday are both required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createWeeklyDraft(allocationId.trim(), weekStart);
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
      <Button variant="primary" onClick={() => setOpen(true)}>
        <Clock className="h-4 w-4" /> New Weekly Timesheet
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
        <Input label="Allocation ID" value={allocationId} onChange={setAllocationId} placeholder="allocation UUID" />
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

  const handleSaveEntries = async () => {
    setBusy(true);
    setError("");
    try {
      const entries = hours
        .map((h, i) => ({
          entry_date: addDays(timesheet.week_starting_date, i),
          hours: Number(h),
          entry_type: "BILLABLE",
        }))
        .filter((e) => e.hours > 0);
      await upsertTimesheetEntries(timesheet.id, entries);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to save entries.");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async () => {
    setBusy(true);
    setError("");
    try {
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

  const editable = timesheet.status === "DRAFT";

  return (
    <div className="rounded-2xl border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-gray-900">{timesheet.employee_name}</div>
          <div className="text-xs text-gray-500">Week of {timesheet.week_starting_date}</div>
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
            <div className="mb-1 text-center text-[11px] font-semibold text-gray-500">{label}</div>
            <input
              type="number"
              min="0"
              max="24"
              value={hours[i]}
              disabled={!editable}
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
        Total: {timesheet.total_hours}h (billable {timesheet.billable_hours}h)
      </div>

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
        {timesheet.status === "SUBMITTED" ? (
          <>
            <Button variant="success" disabled={busy} onClick={handleApprove}>
              <CheckCircle2 className="h-4 w-4" /> Approve
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => setShowReject((v) => !v)}>
              <XCircle className="h-4 w-4" /> Reject
            </Button>
          </>
        ) : null}
        {timesheet.status === "REJECTED" ? (
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

export default function TimesheetsScreen() {
  const [timesheets, setTimesheets] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
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
  };

  useEffect(() => {
    load();
  }, [statusFilter]);

  return (
    <div className="grid gap-4">
      <Card
        title="Timesheets"
        subtitle="Weekly hours per allocation. Submit locks entries pending manager review; approved timesheets are immutable."
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

        <div className="grid gap-3">
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
          ) : timesheets.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">No timesheets yet.</div>
          ) : (
            timesheets.map((t) => <TimesheetCard key={t.id} timesheet={t} onChanged={load} />)
          )}
        </div>
      </Card>
    </div>
  );
}
