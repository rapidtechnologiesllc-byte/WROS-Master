// A leader lets a candidate past an interview round they did not sit (CEO 2026-11-09). The reason is
// required and stays on the candidate's record; the server checks who may do it and refuses a waiver
// over a No Hire, an already passed round or a closed hiring.
import { useState } from "react";
import { Button } from "./ui";
import { waiveRound } from "../services/api/hiringPipeline";

const REASON_MIN = 15; // the server's minimum too (hiring_pipeline_service.WAIVER_REASON_MIN)

export default function RoundWaiverModal({ candidateId, candidateName, level, onClose, onWaived }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const label = level === "L1" ? "L1 (technical)" : "L2 (management)";

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const pipeline = await waiveRound(candidateId, level, reason.trim());
      onWaived(pipeline);
    } catch (err) {
      console.error("[RoundWaiver] Waiver refused:", err);
      setError(err.message || "The waiver was not recorded.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-gray-900">Waive the {label} interview</h3>
        <p className="mt-1 text-sm text-gray-600">
          {candidateName || "The candidate"} moves past {level} without sitting it. Every later step still applies:
          the offer, documents and background check. Your name and reason are kept on their record.
        </p>
        <label className="mt-4 block text-sm font-medium text-gray-700" htmlFor="waiver-reason">Reason</label>
        <textarea
          id="waiver-reason"
          className="mt-1 w-full rounded-xl border px-3 py-2 text-sm"
          rows={4}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Assessed directly by the client's architect on the earlier engagement"
        />
        <div className="mt-1 text-xs text-gray-500">{reason.trim().length < REASON_MIN ? `At least ${REASON_MIN} characters` : " "}</div>
        {error ? (
          <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={submit} disabled={saving || reason.trim().length < REASON_MIN}>
            {saving ? "Recording..." : `Waive ${level}`}
          </Button>
        </div>
      </div>
    </div>
  );
}
