// Executive Signal & Culture Agent -- advisory-only: watches, drafts,
// surfaces. Nothing on this screen acts on a real person without an
// explicit click from whoever's looking at it.
import { useEffect, useState } from "react";
import { X, AlertTriangle, CheckCircle } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import {
  approveRecognition, closeFeedbackCycle, createFeedbackCycle, generateBirthdayDrafts,
  getOrgHealth, getPendingRecognition, rejectRecognition, submitConcern,
} from "../services/api/executiveSignal";

export default function ExecutiveSignalScreen() {
  const [health, setHealth] = useState(null);
  const [pending, setPending] = useState([]);
  const [quarterLabel, setQuarterLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [concernText, setConcernText] = useState("");
  const [submittingConcern, setSubmittingConcern] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const load = async () => {
    setLoading(true);
    setActionError(null);
    try {
      const [h, p] = await Promise.all([getOrgHealth(), getPendingRecognition()]);
      setHealth(h);
      setPending(p);
    } catch (err) {
      setActionError("Could not load Executive Signal data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleGenerateDrafts = async () => {
    setActionError(null);
    setActionSuccess(null);
    try {
      const drafts = await generateBirthdayDrafts();
      setActionSuccess(`${drafts.length} draft(s) generated for review.`);
      load();
    } catch {
      setActionError("Could not generate drafts.");
    }
  };

  const handleApprove = async (id) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await approveRecognition(id);
      setActionSuccess("Approved and sent, signed as you.");
      load();
    } catch (err) {
      setActionError(err.message || "Could not approve.");
    }
  };

  const handleReject = async (id) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await rejectRecognition(id);
      setActionSuccess("Rejected -- not sent.");
      load();
    } catch {
      setActionError("Could not reject.");
    }
  };

  const handleCreateCycle = async () => {
    if (!quarterLabel.trim()) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await createFeedbackCycle(quarterLabel);
      setActionSuccess(`Feedback cycle ${quarterLabel} opened.`);
      setQuarterLabel("");
    } catch {
      setActionError("Could not open cycle.");
    }
  };

  const handleSubmitConcern = async () => {
    const trimmed = concernText.trim();
    if (!trimmed) return;
    setSubmittingConcern(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await submitConcern(trimmed);
      setActionSuccess("Your concern has been raised.");
      setConcernText("");
    } catch (err) {
      setActionError(err.message || "Could not submit your concern.");
    } finally {
      setSubmittingConcern(false);
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">Loading...</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
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
      <Card title="Org Health Snapshot">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-lg border border-gray-200 p-3 text-center">
            <div className="text-xs text-gray-500">Intervention Queue</div>
            <div className="text-lg font-semibold text-gray-900">{health?.recruiting?.intervention_queue?.total ?? "--"}</div>
          </div>
          <div className="rounded-lg border border-gray-200 p-3 text-center">
            <div className="text-xs text-gray-500">Active SLA Breaches</div>
            <div className="text-lg font-semibold text-gray-900">{health?.recruiting?.active_sla_breaches ?? 0}</div>
          </div>
          <div className="rounded-lg border border-gray-200 p-3 text-center">
            <div className="text-xs text-gray-500">Revenue Leakage Flags</div>
            <div className="text-lg font-semibold text-gray-900">{health?.revenue?.active_leakage_flags ?? 0}</div>
          </div>
          <div className="rounded-lg border border-gray-200 p-3 text-center">
            <div className="text-xs text-gray-500">Overdue Tasks</div>
            <div className="text-lg font-semibold text-gray-900">{health?.workforce?.overdue_tasks ?? 0}</div>
          </div>
        </div>
      </Card>

      <Card title="Recognition -- Pending Your Approval" subtitle="Drafted, never sent until you approve. Sent genuinely signed as you.">
        <Button variant="secondary" onClick={handleGenerateDrafts}>Generate Today's Birthday Drafts</Button>
        <div className="mt-3 space-y-2">
          {pending.length === 0 ? (
            <p className="text-sm text-gray-400">Nothing pending.</p>
          ) : (
            pending.map((d) => (
              <div key={d.id} className="border border-bx-border rounded-bx p-3">
                <p className="text-sm text-gray-800">{d.draft_text}</p>
                <div className="flex gap-2 mt-2">
                  <Button onClick={() => handleApprove(d.id)}>Approve &amp; Send</Button>
                  <Button variant="ghost" onClick={() => handleReject(d.id)}>Reject</Button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card title="Quarterly Feedback Cycle">
        <div className="flex gap-2">
          <Input label="Quarter (e.g. 2026-Q3)" value={quarterLabel} onChange={setQuarterLabel} />
          <Button onClick={handleCreateCycle}>Open Cycle</Button>
        </div>
      </Card>

      <Card title="Raise a Concern" subtitle="Sent under your own name to Executive Signal for triage -- not anonymous.">
        <textarea
          value={concernText}
          onChange={(e) => setConcernText(e.target.value)}
          placeholder="What's on your mind?"
          rows={3}
          className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
        />
        <div className="mt-2 flex justify-end">
          <Button onClick={handleSubmitConcern} disabled={submittingConcern || !concernText.trim()}>
            {submittingConcern ? "Submitting…" : "Submit Concern"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
