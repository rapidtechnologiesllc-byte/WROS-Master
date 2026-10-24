import { useCallback, useEffect, useState } from "react";
import { Button } from "./ui";
import cx from "../utils/cx";
import { getEmployeeEscalations, raiseEmployeeEscalation, resolveEmployeeEscalation } from "../services/api/employees";

// Escalations (CEO 2026-10-14): an open one keeps the employee away from every client, Core and
// Staff Aug alike, until a Director or above resolves it with a note. The API decides who may
// resolve; a refusal is shown, not hidden.
export default function EscalationsPanel({ employeeId }) {
  const [rows, setRows] = useState([]);
  const [severities, setSeverities] = useState([]);
  const [reason, setReason] = useState("");
  const [severity, setSeverity] = useState("MEDIUM");
  const [notes, setNotes] = useState({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getEmployeeEscalations(employeeId);
      setRows(data?.escalations || []);
      setSeverities(data?.severities || []);
    } catch (err) {
      console.error("[Escalations] Failed to load:", err);
      setMessage(`Failed to load escalations: ${err.message}`);
    }
  }, [employeeId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (action, done) => {
    setBusy(true);
    setMessage("");
    try {
      await action();
      done();
      await load();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h3 className="mb-1 text-base font-semibold text-gray-900">Escalations</h3>
      <p className="text-xs text-gray-500 mb-3">An open escalation blocks every client submission and deployment.</p>
      {message ? <div className="mb-2 text-xs text-rose-700">{message}</div> : null}
      <div className="space-y-2 mb-3">
        {rows.length === 0 ? <div className="text-sm text-gray-500">No escalations</div> : null}
        {rows.map((e) => (
          <div key={e.id} className={cx("rounded border p-2 text-sm", e.status === "OPEN" ? "bg-rose-50" : "bg-gray-50")}>
            <div className="font-semibold">
              {e.status} · {e.severity}
            </div>
            <div className="text-gray-700">{e.reason}</div>
            {e.status === "OPEN" ? (
              <div className="mt-2 flex gap-2">
                <input
                  value={notes[e.id] || ""}
                  onChange={(ev) => setNotes((prev) => ({ ...prev, [e.id]: ev.target.value }))}
                  placeholder="Resolution note (Director and above)"
                  className="flex-1 rounded border px-2 py-1 text-sm"
                />
                <Button
                  size="sm"
                  disabled={busy || !(notes[e.id] || "").trim()}
                  onClick={() => run(() => resolveEmployeeEscalation(e.id, notes[e.id].trim()),
                    () => setNotes((prev) => ({ ...prev, [e.id]: "" })))}
                >
                  Resolve
                </Button>
              </div>
            ) : (
              <div className="text-xs text-gray-500 mt-1">Resolved: {e.resolution_note}</div>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={reason}
          onChange={(ev) => setReason(ev.target.value)}
          placeholder="Reason for the escalation"
          className="flex-1 rounded border px-2 py-1 text-sm"
        />
        <select value={severity} onChange={(ev) => setSeverity(ev.target.value)} className="rounded border px-2 py-1 text-sm">
          {severities.map((level) => (
            <option key={level} value={level}>{level}</option>
          ))}
        </select>
        <Button
          size="sm"
          variant="danger"
          disabled={busy || reason.trim().length < 3}
          onClick={() => run(() => raiseEmployeeEscalation(employeeId, { reason: reason.trim(), severity }), () => setReason(""))}
        >
          Raise
        </Button>
      </div>
    </div>
  );
}
