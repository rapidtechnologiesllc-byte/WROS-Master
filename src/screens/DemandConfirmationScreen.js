// S-372 (HRMS-0528) Confirmed vs Potential Demand Workflow.
// No Demand/Employee browse screen exists yet in this app (a separate,
// later story in the 205-story queue), so this screen takes a Demand ID
// + Employee ID directly rather than a picker -- consistent with the
// rest of this app's current state, not a shortcut specific to this
// story. Once those browse screens exist, wiring a picker in here is a
// small follow-up, not a redesign.
import { useState } from "react";
import { CalendarCheck2, RefreshCw, Send, CheckCircle2, XCircle, Unlock } from "lucide-react";
import { Card, Button, Input, TextArea } from "../components/ui";
import cx from "../utils/cx";
import {
  confirmDemandWithSOW,
  scheduleAlignmentCall,
  getCallsForDemand,
  confirmFit,
  triggerRelease,
} from "../services/api/demandConfirmation";

function FitRow({ label, confirmed, confirmedAt, notes, onConfirm, disabled }) {
  const [pendingNotes, setPendingNotes] = useState("");

  if (confirmed !== null && confirmed !== undefined) {
    return (
      <div className="rounded-xl border p-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {confirmed ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          ) : (
            <XCircle className="h-4 w-4 text-rose-600" />
          )}
          {label}: {confirmed ? "Confirmed fit" : "Not a fit"}
        </div>
        {notes ? <div className="mt-1 text-xs text-gray-500">{notes}</div> : null}
        <div className="mt-1 text-[11px] text-gray-400">
          Recorded {confirmedAt ? new Date(confirmedAt).toLocaleString() : ""} -- immutable, cannot be changed here.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-dashed p-3">
      <div className="mb-2 text-sm font-semibold text-gray-700">{label}: not yet recorded</div>
      <TextArea value={pendingNotes} onChange={setPendingNotes} placeholder="Notes (optional)" rows={2} />
      <div className="mt-2 flex gap-2">
        <Button variant="success" disabled={disabled} onClick={() => onConfirm(true, pendingNotes)}>
          <CheckCircle2 className="h-4 w-4" /> Confirm fit
        </Button>
        <Button variant="danger" disabled={disabled} onClick={() => onConfirm(false, pendingNotes)}>
          <XCircle className="h-4 w-4" /> Not a fit
        </Button>
      </div>
    </div>
  );
}

function CallCard({ call, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const runFit = async (participant, confirmed, notes) => {
    setBusy(true);
    setError("");
    try {
      await confirmFit(call.id, { participant, confirmed, notes });
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to record confirmation.");
    } finally {
      setBusy(false);
    }
  };

  const runRelease = async () => {
    setBusy(true);
    setError("");
    try {
      await triggerRelease(call.id);
      onChanged();
    } catch (err) {
      setError(err.message || "Release blocked.");
    } finally {
      setBusy(false);
    }
  };

  const canRelease =
    call.employee_fit_confirmed === true &&
    call.bu_head_fit_confirmed === true &&
    !call.specialty_client_release_triggered_at;

  return (
    <div className="rounded-2xl border p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="font-semibold text-gray-900">{call.employee_name}</div>
          <div className="text-xs text-gray-500">→ {call.demand_job_title}</div>
        </div>
        {call.specialty_client_release_triggered_at ? (
          <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
            Released
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <FitRow
          label="Employee"
          confirmed={call.employee_fit_confirmed}
          confirmedAt={call.employee_fit_confirmed_at}
          notes={call.employee_fit_notes}
          disabled={busy}
          onConfirm={(confirmed, notes) => runFit("EMPLOYEE", confirmed, notes)}
        />
        <FitRow
          label="BU Head"
          confirmed={call.bu_head_fit_confirmed}
          confirmedAt={call.bu_head_fit_confirmed_at}
          notes={call.bu_head_fit_notes}
          disabled={busy}
          onConfirm={(confirmed, notes) => runFit("BU_HEAD", confirmed, notes)}
        />
      </div>

      {!call.specialty_client_release_triggered_at ? (
        <div className="mt-3">
          <Button variant="primary" disabled={busy || !canRelease} onClick={runRelease}>
            <Unlock className="h-4 w-4" /> Trigger Specialty client release
          </Button>
          {!canRelease ? (
            <div className="mt-1 text-xs text-gray-500">
              Needs the demand confirmed with an SOW, plus both fit confirmations, before release unlocks.
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function DemandConfirmationScreen() {
  const [demandId, setDemandId] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [sowReference, setSowReference] = useState("");
  const [sowDate, setSowDate] = useState("");
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshCalls = async () => {
    if (!demandId.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await getCallsForDemand(demandId.trim());
      setCalls(res?.calls || []);
    } catch (err) {
      setError(err.message || "Failed to load alignment calls for this demand.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmSOW = async () => {
    if (!demandId.trim() || !sowReference.trim()) {
      setError("Demand ID and SOW reference are both required.");
      return;
    }
    setError("");
    setNotice("");
    try {
      await confirmDemandWithSOW(demandId.trim(), {
        sowReference: sowReference.trim(),
        sowReceivedDate: sowDate || undefined,
      });
      setNotice("Demand confirmed with SOW.");
    } catch (err) {
      setError(err.message || "Failed to confirm SOW.");
    }
  };

  const handleScheduleCall = async () => {
    if (!demandId.trim() || !employeeId.trim()) {
      setError("Demand ID and Employee ID are both required.");
      return;
    }
    setError("");
    setNotice("");
    try {
      await scheduleAlignmentCall(demandId.trim(), employeeId.trim());
      setNotice("Alignment call scheduled (or an existing one was reused).");
      await refreshCalls();
    } catch (err) {
      setError(err.message || "Failed to schedule alignment call.");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Confirmed vs Potential Demand Workflow"
        subtitle="Record the SOW for a demand, schedule the 3-way alignment call, and track both fit confirmations before releasing to the Specialty client."
        icon={<CalendarCheck2 className="h-4 w-4" />}
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Demand ID" value={demandId} onChange={setDemandId} placeholder="demand UUID" />
          <Input label="Employee ID" value={employeeId} onChange={setEmployeeId} placeholder="employee UUID" />
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Input label="SOW reference" value={sowReference} onChange={setSowReference} placeholder="SOW-2026-001" />
          <Input label="SOW received date" type="date" value={sowDate} onChange={setSowDate} />
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={handleConfirmSOW}>
            <CheckCircle2 className="h-4 w-4" /> Confirm demand with SOW
          </Button>
          <Button variant="primary" onClick={handleScheduleCall}>
            <Send className="h-4 w-4" /> Schedule alignment call
          </Button>
          <Button variant="ghost" onClick={refreshCalls} disabled={!demandId.trim()}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Load calls for this demand
          </Button>
        </div>
      </Card>

      {calls.length > 0 ? (
        <div className="grid gap-3">
          {calls.map((call) => (
            <CallCard key={call.id} call={call} onChanged={refreshCalls} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
