// Employee self-service timesheet -- real ownership boundary added
// 2026-08-04 (app.services.employee_self_service) on top of the
// already-real, already-tested HR-operated timesheet engine. Every
// employee only ever sees/edits their OWN allocation and timesheet.
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Card, Button, Select } from "../components/ui";
import {
  getMyAllocations, getMyCurrentTimesheet, getMyTimesheetHistory, logMyHours, submitMyTimesheet,
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
    return d.toISOString().slice(0, 10);
  });
}

export default function MyTimesheetScreen() {
  const [allocations, setAllocations] = useState([]);
  const [allocationId, setAllocationId] = useState("");
  const [timesheet, setTimesheet] = useState(null);
  const [hours, setHours] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadAllocations = async () => {
    try {
      const allocs = await getMyAllocations();
      setAllocations(allocs || []);
      if (allocs?.length) setAllocationId(allocs[0].id);
    } catch {
      toast.error("Could not load your project allocations.");
    } finally {
      setLoading(false);
    }
  };

  const loadTimesheet = async (id) => {
    if (!id) return;
    try {
      const ts = await getMyCurrentTimesheet(id);
      setTimesheet(ts);
      const byDate = {};
      (ts.entries || []).forEach((e) => { byDate[e.entry_date] = String(e.hours); });
      setHours(byDate);
    } catch {
      toast.error("Could not load this week's timesheet.");
    }
  };

  const loadHistory = async () => {
    try {
      setHistory(await getMyTimesheetHistory());
    } catch {
      // non-critical -- history is a secondary view
    }
  };

  useEffect(() => {
    loadAllocations();
    loadHistory();
  }, []);

  useEffect(() => {
    if (allocationId) loadTimesheet(allocationId);
  }, [allocationId]);

  const handleSave = async () => {
    if (!timesheet) return;
    setSaving(true);
    try {
      const entries = weekDays(timesheet.week_starting_date)
        .filter((d) => hours[d] !== undefined && hours[d] !== "")
        .map((d) => ({ entry_date: d, hours: Number(hours[d]), entry_type: "BILLABLE" }));
      const updated = await logMyHours(timesheet.id, entries);
      setTimesheet(updated);
      toast.success("Hours saved.");
    } catch (err) {
      toast.error(err.message || "Could not save hours.");
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!timesheet) return;
    try {
      const submitted = await submitMyTimesheet(timesheet.id);
      setTimesheet(submitted);
      toast.success("Timesheet submitted for approval.");
      loadHistory();
    } catch (err) {
      toast.error(err.message || "Could not submit timesheet.");
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading...</div>;

  if (allocations.length === 0) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <h1 className="text-xl font-bold text-bx-navy mb-2">My Timesheet</h1>
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-bx-navy">My Timesheet</h1>
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
