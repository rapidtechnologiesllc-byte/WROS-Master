// Employee self-service timesheet -- real ownership boundary added
// 2026-08-04 (app.services.employee_self_service) on top of the
// already-real, already-tested HR-operated timesheet engine. Every
// employee only ever sees/edits their OWN allocation and timesheet.
import { useCallback, useEffect, useState } from "react";
import { X, AlertTriangle, CheckCircle } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import {
  getMyAllocations, getMyTimesheetForWeek, getMyTimesheetHistory, getMyTimesheetWeeks, logMyHours, submitMyTimesheet,
} from "../services/api/myTimesheet";

const STATUS_STYLES = {
  DRAFT: "bg-gray-100 text-gray-600 border-gray-200",
  SUBMITTED: "bg-amber-100 text-amber-800 border-amber-300",
  APPROVED: "bg-emerald-100 text-emerald-800 border-emerald-300",
  REJECTED: "bg-red-100 text-red-800 border-red-300",
  DISPUTED: "bg-purple-100 text-purple-800 border-purple-300",
};

function weekDays(weekStartingDate) {
  const start = new Date(`${weekStartingDate}T00:00:00`);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${month}-${day}`;
  });
}

function weekLabel(monday, index) {
  if (index === 0) return `This week (from ${monday})`;
  if (index === 1) return `Last week (from ${monday})`;
  return `Week of ${monday}`;
}

export default function MyTimesheetScreen() {
  const [allocations, setAllocations] = useState([]);
  const [allocationId, setAllocationId] = useState("");
  const [weeks, setWeeks] = useState([]);
  const [week, setWeek] = useState("");
  const [timesheet, setTimesheet] = useState(null);
  const [hours, setHours] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // the server's own reason when this login has no employee record (404), shown instead of the screen
  const [notLinked, setNotLinked] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getMyTimesheetHistory());
    } catch (err) {
      setActionError(`Could not load your recent timesheets: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setActionError(null);
      try {
        const [allocs, allowedWeeks] = await Promise.all([getMyAllocations(), getMyTimesheetWeeks()]);
        setAllocations(allocs);
        setWeeks(allowedWeeks);
        if (allocs.length) setAllocationId(allocs[0].id);
        if (allowedWeeks.length) setWeek(allowedWeeks[0]);
        await loadHistory();
      } catch (err) {
        if (err.status === 404) {
          setNotLinked(err.message);
        } else {
          setActionError(`Could not load your project allocations: ${err.message}`);
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [loadHistory]);

  useEffect(() => {
    if (!allocationId || !week) return;
    const loadTimesheet = async () => {
      setActionError(null);
      setTimesheet(null);
      try {
        const ts = await getMyTimesheetForWeek(allocationId, week);
        setTimesheet(ts);
        const byDate = {};
        (ts.entries || []).forEach((e) => { byDate[e.entry_date] = String(e.hours); });
        setHours(byDate);
      } catch (err) {
        setActionError(`Could not open the week of ${week}: ${err.message}`);
      }
    };
    loadTimesheet();
  }, [allocationId, week]);

  const handleSave = async () => {
    if (!timesheet) return;
    setSaving(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const entries = weekDays(timesheet.week_starting_date)
        .filter((d) => hours[d] !== undefined && hours[d] !== "")
        .map((d) => ({ entry_date: d, hours: Number(hours[d]), entry_type: "BILLABLE" }));
      const updated = await logMyHours(timesheet.id, entries);
      setTimesheet(updated);
      setActionSuccess("Hours saved.");
    } catch (err) {
      setActionError(err.message || "Could not save hours.");
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!timesheet) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      const submitted = await submitMyTimesheet(timesheet.id);
      setTimesheet(submitted);
      setActionSuccess("Timesheet submitted for approval.");
      loadHistory();
    } catch (err) {
      setActionError(err.message || "Could not submit timesheet.");
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading...</div>;

  if (notLinked) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Card>
          <p className="text-sm text-gray-700">{notLinked}</p>
        </Card>
      </div>
    );
  }

  if (allocations.length === 0 && !actionError) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Card>
          <p className="text-sm text-gray-500">You're not currently allocated to an active project, so there's no timesheet to fill yet.</p>
        </Card>
      </div>
    );
  }

  const days = timesheet ? weekDays(timesheet.week_starting_date) : [];
  const total = days.reduce((sum, d) => sum + (Number(hours[d]) || 0), 0);
  const editable = timesheet && timesheet.status === "DRAFT";

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {actionError && (
        <div className="flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">{actionError}</p>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="flex-shrink-0 text-red-400 hover:text-red-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}
      {actionSuccess && (
        <div className="flex items-start gap-3 rounded-lg bg-green-50 px-4 py-3 border border-green-200">
          <CheckCircle className="h-5 w-5 flex-shrink-0 text-green-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">{actionSuccess}</p>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            className="flex-shrink-0 text-green-400 hover:text-green-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        {weeks.length > 1 && (
          <div className="w-64">
            <Select
              value={week}
              onChange={setWeek}
              options={weeks.map((w, i) => ({ value: w, label: weekLabel(w, i) }))}
            />
          </div>
        )}
        {allocations.length > 1 && (
          <div className="w-64">
            <Select
              value={allocationId}
              onChange={setAllocationId}
              options={allocations.map((a) => ({ value: a.id, label: `${a.demand_job_title} (${a.role || "assigned"})` }))}
            />
          </div>
        )}
      </div>

      {timesheet && (
        <Card
          title={`Week of ${timesheet.week_starting_date}`}
          right={
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-bx border ${STATUS_STYLES[timesheet.status] || ""}`}>
              {timesheet.status}
            </span>
          }
        >
          {timesheet.status === "REJECTED" && timesheet.rejection_reason && (
            <div className="mb-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-bx px-3 py-2">
              Rejected: {timesheet.rejection_reason}
            </div>
          )}
          <div className="grid grid-cols-7 gap-2 mb-4">
            {days.map((d) => (
              <div key={d} className="text-center">
                <div className="text-[10px] uppercase text-gray-500 mb-1">
                  {new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" })}
                </div>
                <input
                  type="number"
                  min="0"
                  max="24"
                  step="0.5"
                  disabled={!editable}
                  className="w-full text-center text-sm border border-bx-border rounded-bx px-1 py-2 outline-none focus:border-bx-orange disabled:bg-bx-light disabled:text-gray-400"
                  value={hours[d] ?? ""}
                  onChange={(e) => setHours({ ...hours, [d]: e.target.value })}
                />
              </div>
            ))}
          </div>
          <p className="text-sm text-gray-600 mb-3">Total: <span className="font-semibold text-bx-navy">{total}</span> hours</p>
          {editable && (
            <div className="flex gap-2">
              <Button variant="secondary" disabled={saving} onClick={handleSave}>{saving ? "Saving..." : "Save"}</Button>
              <Button disabled={saving || total === 0} onClick={handleSubmit}>Submit for Approval</Button>
            </div>
          )}
        </Card>
      )}

      <Card title="Recent Timesheets">
        {history.length === 0 ? (
          <p className="text-sm text-gray-400">No history yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1.5 pr-3">Week</th>
                <th className="py-1.5 pr-3">Hours</th>
                <th className="py-1.5 pr-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-t border-bx-border">
                  <td className="py-1.5 pr-3">{h.week_starting_date}</td>
                  <td className="py-1.5 pr-3">{h.total_hours}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-bx border ${STATUS_STYLES[h.status] || ""}`}>{h.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
