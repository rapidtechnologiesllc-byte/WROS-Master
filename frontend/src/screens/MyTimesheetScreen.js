// Employee self-service timesheet: every employee enters and submits only their OWN time
// (app.services.employee_self_service).
// CEO 2026-11-11: one weekly time card. A row per thing the time went to -- a client placement
// (Staff Aug), a project, or, on the bench, a work item a BU head approved (accelerator,
// certification, other work) -- and a column per day with its date; totals per row and per day.
// "Submit week" sends what is typed. Each row shows where it stands: reporting manager ->
// Finance -> invoice. Behind the card each row is its own timesheet (one per placement or work
// item and week), so approval, invoicing and the P&L work as before.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { X, AlertTriangle, CheckCircle } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import {
  getMyAllocations, getMyTimesheetForWeek, getMyTimesheetHistory, getMyTimesheetWeeks, getMyWorkItems, logMyHours,
  submitMyTimesheet,
} from "../services/api/myTimesheet";
import { dayDate, dayName, todayIso, weekDays, weekRange, WORK_TYPE_STYLES } from "../utils/timesheetWeek";

const STATUS_STYLES = {
  DRAFT: "bg-gray-100 text-gray-600 border-gray-200",
  SUBMITTED: "bg-amber-100 text-amber-800 border-amber-300",
  APPROVED: "bg-emerald-100 text-emerald-800 border-emerald-300",
  REJECTED: "bg-red-100 text-red-800 border-red-300",
  DISPUTED: "bg-purple-100 text-purple-800 border-purple-300",
};
// client and project work first, then bench work, then internal tasks
const ROW_ORDER = { STAFF_AUG: 0, PROJECT: 1, BENCH: 2, INTERNAL_TASK: 3 };

function weekLabel(monday, index) {
  if (index === 0) return `This week (${weekRange(monday)})`;
  if (index === 1) return `Last week (${weekRange(monday)})`;
  return `Week of ${weekRange(monday)}`;
}

const isEditable = (sheet) => sheet.status === "DRAFT" || sheet.status === "REJECTED";
const hoursOf = (sheet) => Object.fromEntries((sheet.entries || []).map((e) => [e.entry_date, String(e.hours)]));
const sortRows = (rows) => [...rows].sort((a, b) => (ROW_ORDER[a.work_type] ?? 9) - (ROW_ORDER[b.work_type] ?? 9)
  || String(a.work_label).localeCompare(String(b.work_label)));

export default function MyTimesheetScreen() {
  const [allocations, setAllocations] = useState([]);
  const [workItems, setWorkItems] = useState([]);
  const [weeks, setWeeks] = useState([]);
  const [week, setWeek] = useState("");
  // the week's rows: one timesheet per placement / work item; hours[timesheetId][date] = what is typed
  const [rows, setRows] = useState(null);
  const [hours, setHours] = useState({});
  const [responses, setResponses] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // the server's own reason when this login has no employee record (404), shown instead of the screen
  const [notLinked, setNotLinked] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  // a resubmit task links here with ?week=YYYY-MM-DD (&work_item=<id> for bench work)
  const [searchParams] = useSearchParams();
  const linkedWeek = searchParams.get("week");
  const linkedWorkItem = searchParams.get("work_item");

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
        const [allocs, allowedWeeks, items] = await Promise.all(
          [getMyAllocations(), getMyTimesheetWeeks(), getMyWorkItems()]);
        setAllocations(allocs);
        setWorkItems(items);
        setWeeks(allowedWeeks);
        if (allowedWeeks.length) setWeek(allowedWeeks.includes(linkedWeek) ? linkedWeek : allowedWeeks[0]);
        await loadHistory();
      } catch (err) {
        if (err.status === 404) {
          setNotLinked(err.message);
        } else {
          setActionError(`Could not load your timesheet: ${err.message}`);
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [loadHistory, linkedWeek]);

  const showRows = useCallback((sheets) => {
    setRows(sortRows(sheets));
    setHours(Object.fromEntries(sheets.map((s) => [s.id, hoursOf(s)])));
  }, []);

  // The week's card: a row for each of my placements (its draft is started when missing), plus the
  // rows already on the week (bench work, a placement that has since ended).
  const loadWeek = useCallback(async () => {
    if (!week) return;
    setRows(null);
    setActionError(null);
    try {
      // a placement the week falls outside of (not started yet, already ended) simply has no row
      await Promise.all(allocations.map((a) => getMyTimesheetForWeek({ allocationId: a.id }, week).catch(() => null)));
      if (linkedWorkItem && linkedWeek === week) {
        await getMyTimesheetForWeek({ workItemId: linkedWorkItem }, week).catch(() => null);
      }
      showRows(await getMyTimesheetHistory(week));
    } catch (err) {
      setRows([]);
      setActionError(`Could not open the week of ${weekRange(week)}: ${err.message}`);
    }
  }, [week, allocations, linkedWorkItem, linkedWeek, showRows]);

  useEffect(() => {
    if (!loading && !notLinked) loadWeek();
  }, [loading, notLinked, loadWeek]);

  const days = useMemo(() => (week ? weekDays(week) : []), [week]);
  const today = todayIso();
  const typed = (sheet, day) => Number(hours[sheet.id]?.[day]) || 0;
  const rowTotal = (sheet) => days.reduce((sum, d) => sum + typed(sheet, d), 0);
  const dayTotal = (day) => (rows || []).reduce((sum, s) => sum + typed(s, day), 0);
  const weekTotal = (rows || []).reduce((sum, s) => sum + rowTotal(s), 0);
  const editableRows = (rows || []).filter(isEditable);
  // every day that is typed or was saved before, so a day cleared on the card is cleared on the server
  const entriesOf = (sheet) => days
    .filter((d) => typed(sheet, d) > 0 || (sheet.entries || []).some((e) => e.entry_date === d))
    .map((d) => ({ entry_date: d, hours: typed(sheet, d), entry_type: "BILLABLE" }));
  const changed = (sheet) => days.some((d) => typed(sheet, d) !== (Number(hoursOf(sheet)[d]) || 0));

  const replaceRow = (updated) => setRows((current) => sortRows(current.map((s) => (s.id === updated.id ? updated : s))));

  // bench work not on the card yet
  const addable = workItems.filter((i) => !(rows || []).some((s) => s.work_item_id === i.id));
  const addBenchRow = async (workItemId) => {
    if (!workItemId) return;
    setActionError(null);
    try {
      const sheet = await getMyTimesheetForWeek({ workItemId }, week);
      setRows((current) => sortRows([...(current || []).filter((s) => s.id !== sheet.id), sheet]));
      setHours((current) => ({ ...current, [sheet.id]: hoursOf(sheet) }));
    } catch (err) {
      setActionError(err.message || "Could not add that work item to the week.");
    }
  };

  const run = async (work, done) => {
    setSaving(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await work();
      setActionSuccess(done);
      loadHistory();
    } catch (err) {
      setActionError(err.message || "That did not go through.");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => run(async () => {
    const saved = await Promise.all(editableRows.filter(changed).map((sheet) => logMyHours(sheet.id, entriesOf(sheet))));
    saved.forEach(replaceRow);
  }, "Hours saved.");

  // Submit sends what is on the card: each row with hours is saved, then submitted to the approver.
  // A rejected row with no change goes back with the response typed under it.
  const handleSubmit = () => run(async () => {
    const sending = editableRows.filter((s) => rowTotal(s) > 0);
    if (!sending.length) throw new Error("Enter the hours you worked before submitting.");
    const submitted = await Promise.all(sending.map(async (sheet) => {
      if (changed(sheet)) await logMyHours(sheet.id, entriesOf(sheet));
      return submitMyTimesheet(sheet.id, (responses[sheet.id] || "").trim());
    }));
    submitted.forEach(replaceRow);
    setResponses({});
  }, "Submitted. Each row went to your reporting manager for approval.");

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

  const nothingToLogAgainst = allocations.length === 0 && workItems.length === 0 && rows && rows.length === 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {actionError && (
        <div className="flex items-start gap-3 rounded-lg bg-red-50 px-4 py-3 border border-red-200">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">{actionError}</p>
          </div>
          <button type="button" onClick={() => setActionError(null)} className="flex-shrink-0 text-red-400 hover:text-red-600">
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
          <button type="button" onClick={() => setActionSuccess(null)} className="flex-shrink-0 text-green-400 hover:text-green-600">
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <Card
        title={week ? `My time card: ${weekRange(week)}` : "My time card"}
        right={weeks.length > 1 ? (
          <div className="w-72">
            <Select value={week} onChange={setWeek} options={weeks.map((w, i) => ({ value: w, label: weekLabel(w, i) }))} />
          </div>
        ) : null}
      >
        {rows === null ? (
          <p className="text-sm text-gray-500">Loading the week…</p>
        ) : nothingToLogAgainst ? (
          <p className="text-sm text-gray-500">
            You're not allocated to a client or project, and your business unit has no bench work item yet (an
            accelerator, a certification or other approved work). Ask your BU head to add the work item you are on;
            your time is logged against it.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500">
                    <th className="py-2 pr-3 text-left font-semibold">Time for</th>
                    {days.map((d) => (
                      <th key={d} className="px-1 py-2 text-center font-semibold">
                        {dayName(d)}<div className="font-normal">{dayDate(d)}</div>
                      </th>
                    ))}
                    <th className="px-2 py-2 text-right font-semibold">Total</th>
                    <th className="py-2 pl-3 text-left font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((sheet) => {
                    const editable = isEditable(sheet);
                    const flagged = sheet.rejection?.flagged_dates || [];
                    return (
                      <tr key={sheet.id} className="border-t border-bx-border align-top">
                        <td className="py-2 pr-3">
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${WORK_TYPE_STYLES[sheet.work_type] || ""}`}>
                            {sheet.work_group || "Time"}
                          </span>
                          <div className="mt-1 text-gray-900">{sheet.work_label}</div>
                          {sheet.pipeline?.text && <div className="mt-0.5 text-xs text-gray-500">{sheet.pipeline.text}</div>}
                          {sheet.rejection && (
                            <div className="mt-1 rounded-bx border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                              <div className="font-semibold">Rejected: {sheet.rejection.reason}</div>
                              {flagged.length ? <div>Days to fix: {flagged.join(", ")}</div> : null}
                              {editable && (
                                <textarea
                                  className="mt-1 w-full rounded-bx border border-bx-border px-2 py-1 text-xs text-gray-900"
                                  rows={2}
                                  placeholder="Change the hours, or explain here why they are right, then submit again"
                                  value={responses[sheet.id] || ""}
                                  onChange={(e) => setResponses({ ...responses, [sheet.id]: e.target.value })}
                                />
                              )}
                            </div>
                          )}
                        </td>
                        {days.map((d) => (
                          <td key={d} className="px-1 py-2">
                            <input
                              aria-label={`${sheet.work_label} ${dayName(d)} ${dayDate(d)}`}
                              title={flagged.includes(d) ? "Flagged by your approver"
                                : d > today ? "This day has not happened yet: hours are logged once worked" : undefined}
                              type="number"
                              min="0"
                              max="24"
                              step="0.5"
                              disabled={!editable || d > today}
                              className={`w-16 text-center text-sm border rounded-bx px-1 py-2 outline-none focus:border-bx-orange disabled:bg-bx-light disabled:text-gray-400 ${flagged.includes(d) ? "border-red-500 bg-red-50" : "border-bx-border"}`}
                              value={hours[sheet.id]?.[d] ?? ""}
                              onChange={(e) => setHours({ ...hours, [sheet.id]: { ...hours[sheet.id], [d]: e.target.value } })}
                            />
                          </td>
                        ))}
                        <td className="px-2 py-2 text-right font-semibold text-bx-navy">{rowTotal(sheet)}</td>
                        <td className="py-2 pl-3">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-bx border ${STATUS_STYLES[sheet.status] || ""}`}>
                            {sheet.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-bx-border text-sm font-semibold text-bx-navy">
                    <td className="py-2 pr-3 text-right">Totals</td>
                    {days.map((d) => <td key={d} className="px-1 py-2 text-center">{dayTotal(d) || ""}</td>)}
                    <td className="px-2 py-2 text-right">{weekTotal}</td>
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
              <div className="w-96 max-w-full">
                {addable.length > 0 ? (
                  <Select
                    label="Add bench work to this week"
                    value=""
                    onChange={addBenchRow}
                    options={[{ value: "", label: "Pick an accelerator, certification or approved work…" },
                      ...addable.map((i) => ({ value: i.id, label: `${i.category_label} · ${i.name}` }))]}
                  />
                ) : (
                  <p className="text-xs text-gray-500">
                    {workItems.length ? "Every bench work item open to you is on the card."
                      : "No bench work item is open to you. On the bench, ask your BU head to add the one you are working on."}
                  </p>
                )}
              </div>
              {editableRows.length > 0 && (
                <div className="flex gap-2">
                  <Button variant="secondary" disabled={saving} onClick={handleSave}>{saving ? "Working..." : "Save"}</Button>
                  <Button disabled={saving || editableRows.every((s) => rowTotal(s) === 0)} onClick={handleSubmit}>
                    Submit week for approval
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </Card>

      <Card title="Recent Timesheets">
        {history.length === 0 ? (
          <p className="text-sm text-gray-400">No history yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1.5 pr-3">Week</th>
                <th className="py-1.5 pr-3">Time for</th>
                <th className="py-1.5 pr-3">Hours</th>
                <th className="py-1.5 pr-3">Status</th>
                <th className="py-1.5 pr-3">Where it stands</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-t border-bx-border">
                  <td className="py-1.5 pr-3 whitespace-nowrap">{weekRange(h.week_starting_date)}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`mr-1 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${WORK_TYPE_STYLES[h.work_type] || ""}`}>
                      {h.work_group}
                    </span>
                    <span className="text-xs text-gray-600">{h.work_label}</span>
                  </td>
                  <td className="py-1.5 pr-3">{h.total_hours}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-bx border ${STATUS_STYLES[h.status] || ""}`}>{h.status}</span>
                  </td>
                  <td className="py-1.5 pr-3 text-xs text-gray-600">{h.pipeline?.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
