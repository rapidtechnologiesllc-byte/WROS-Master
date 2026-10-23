// Timesheet approval (CEO 2026-10-22): the approver opens this from the approval task, the Flash
// decision or the email. /timesheet-approvals lists what waits for me; /timesheet-approvals/:id
// shows the week, the previous rejection, the employee's response and what changed, and lets the
// approver approve (with a comment; a resubmission needs the "addressed" confirmation) or reject
// with a reason, flagging the days at fault.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, XCircle, ArrowLeft } from "lucide-react";
import { Button, Card } from "../components/ui";
import cx from "../utils/cx";
import {
  approveTimesheetReview, getMyTimesheetApprovals, getTimesheetApproval, rejectTimesheetReview,
} from "../services/api/timesheetApprovals";

const MIN_REASON = 20; // the server's rule (RejectTimesheetRequest); shown so nobody types blind

function ApprovalList() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    getMyTimesheetApprovals().then(setRows).catch((err) => setError(err.message));
  }, []);
  return (
    <Card title="Timesheets waiting for your approval">
      {error ? <div className="text-sm text-rose-700">{error}</div> : null}
      {rows && rows.length === 0 ? <div className="text-sm text-gray-500">Nothing is waiting for you.</div> : null}
      <ul className="divide-y">
        {(rows || []).map((r) => (
          <li key={r.timesheet_id} className="py-2 text-sm">
            <Link className="font-semibold text-blue-700 hover:underline" to={`/timesheet-approvals/${r.timesheet_id}`}>
              {r.employee_name}: week of {r.week_starting_date} ({r.total_hours}h)
            </Link>
            {r.revision > 1 ? <span className="ml-2 text-xs text-amber-700">revision {r.revision}</span> : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ApprovalDetail({ timesheetId }) {
  const [view, setView] = useState(null);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [addressed, setAddressed] = useState(false);
  const [reason, setReason] = useState("");
  const [flagged, setFlagged] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      setView(await getTimesheetApproval(timesheetId));
    } catch (err) {
      setError(err.message);
    }
  }, [timesheetId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (action) => {
    setBusy(true);
    setError("");
    try {
      setView(await action());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (day) => setFlagged((f) => (f.includes(day) ? f.filter((d) => d !== day) : [...f, day]));
  if (!view) return <Card>{error ? <div className="text-sm text-rose-700">{error}</div> : "Loading…"}</Card>;
  const previousFlags = view.previous_rejection?.flagged_dates || [];

  return (
    <div className="grid gap-4">
      <Card
        title={`${view.employee_name}: week of ${view.week_starting_date}`}
        subtitle={`${view.total_hours} hours · ${view.status}${view.revision > 1 ? ` · revision ${view.revision}` : ""}`}
      >
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
        {view.previous_rejection ? (
          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
            <div className="font-semibold text-amber-900">Previously rejected: {view.previous_rejection.reason}</div>
            {previousFlags.length ? <div className="text-amber-800">Days flagged: {previousFlags.join(", ")}</div> : null}
            <div className="mt-1 text-gray-800">
              Employee's response: {view.employee_response || <span className="italic">none (they changed the entries)</span>}
            </div>
          </div>
        ) : null}
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr><th className="py-1">Day</th><th>Hours</th><th>Type</th><th>Notes</th>{view.may_decide ? <th>Flag</th> : null}</tr>
          </thead>
          <tbody className="divide-y">
            {view.entries.map((e) => (
              <tr key={e.entry_date} className={cx(previousFlags.includes(e.entry_date) ? "bg-amber-50" : "")}>
                <td className="py-1">{e.entry_date}</td>
                <td>{e.hours}</td>
                <td>{e.entry_type}</td>
                <td className="text-gray-600">{e.notes || "—"}</td>
                {view.may_decide ? (
                  <td><input type="checkbox" checked={flagged.includes(e.entry_date)} onChange={() => toggle(e.entry_date)} /></td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
        {view.changes_since_rejection.length ? (
          <div className="mt-3 text-sm">
            <div className="font-semibold">Changed since the rejection</div>
            <ul className="text-gray-700">
              {view.changes_since_rejection.map((c) => (
                <li key={c.entry_date}>
                  {c.entry_date}: {c.change} — {c.before ? `${c.before.hours}h` : "nothing"} → {c.after ? `${c.after.hours}h` : "nothing"}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      {view.may_decide ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Approve">
            <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={2} placeholder="Comment (optional)"
              value={comment} onChange={(e) => setComment(e.target.value)} />
            {view.requires_addressed_confirmation ? (
              <label className="mt-2 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={addressed} onChange={(e) => setAddressed(e.target.checked)} />
                The earlier rejection is addressed
              </label>
            ) : null}
            <Button className="mt-2" variant="primary"
              disabled={busy || (view.requires_addressed_confirmation && !addressed)}
              onClick={() => run(() => approveTimesheetReview(timesheetId, { comment, addressed }))}>
              <CheckCircle2 className="h-4 w-4" /> Approve
            </Button>
          </Card>
          <Card title="Reject">
            <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={2}
              placeholder={`Reason (required, at least ${MIN_REASON} characters)`}
              value={reason} onChange={(e) => setReason(e.target.value)} />
            <div className="text-xs text-gray-500">{flagged.length ? `Flagged: ${flagged.join(", ")}` : "Tick days above to flag them."}</div>
            <Button className="mt-2" variant="danger" disabled={busy || reason.trim().length < MIN_REASON}
              onClick={() => run(() => rejectTimesheetReview(timesheetId, { reason: reason.trim(), flaggedDates: flagged }))}>
              <XCircle className="h-4 w-4" /> Reject
            </Button>
          </Card>
        </div>
      ) : (
        <Card><div className="text-sm text-gray-600">Decision: {view.decision || "none"}. Nothing for you to do here.</div></Card>
      )}

      <Card title="History">
        <ul className="text-sm">
          {view.history.map((h) => (
            <li key={h.revision}>
              Revision {h.revision}: {h.decision}{h.note ? ` — ${h.note}` : ""}{h.addressed_confirmed ? " (rejection addressed)" : ""}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

export default function TimesheetApprovalScreen() {
  const { timesheetId } = useParams();
  return (
    <div className="grid gap-4">
      {timesheetId ? (
        <Link to="/timesheet-approvals" className="flex items-center gap-1 text-sm font-semibold text-blue-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> All my approvals
        </Link>
      ) : null}
      {timesheetId ? <ApprovalDetail timesheetId={timesheetId} /> : <ApprovalList />}
    </div>
  );
}
