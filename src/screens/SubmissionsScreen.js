// HRMS-0711 Client Submission Pipeline. No Demand/Candidate picker
// exists yet in this app for this flow, so entry is by ID -- same
// pattern/rationale as DemandConfirmationScreen.
import { useEffect, useState } from "react";
import { Send, RefreshCw, AlertTriangle } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import cx from "../utils/cx";
import {
  submitCandidate,
  getSubmissions,
  getSubmissionViolations,
  recordClientResponse,
} from "../services/api/submissions";

const NEXT_STATUS_OPTIONS = {
  SUBMITTED: ["SHORTLISTED", "CLIENT_INTERVIEW_REQUESTED", "REJECTED_BY_CLIENT", "WITHDRAWN"],
  SHORTLISTED: ["CLIENT_INTERVIEW_REQUESTED", "REJECTED_BY_CLIENT", "WITHDRAWN"],
  CLIENT_INTERVIEW_REQUESTED: ["OFFER_EXTENDED", "REJECTED_BY_CLIENT", "WITHDRAWN"],
  OFFER_EXTENDED: ["PLACED", "REJECTED_BY_CLIENT", "WITHDRAWN"],
};

function SubmissionRow({ submission, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const options = NEXT_STATUS_OPTIONS[submission.status] || [];

  const handleTransition = async (status) => {
    setBusy(true);
    setError("");
    try {
      await recordClientResponse(submission.id, status);
      onChanged();
    } catch (err) {
      setError(err.message || "Failed to record client response.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3 text-gray-900">
        <div className="font-semibold">{submission.candidate_name}</div>
        <div className="text-xs text-gray-500">→ {submission.demand_job_title}</div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-700">{submission.status}</td>
      <td className="px-4 py-3">
        {error ? <div className="mb-1 text-xs text-rose-700">{error}</div> : null}
        <div className="flex flex-wrap gap-1">
          {options.map((status) => (
            <Button
              key={status}
              variant={status === "PLACED" ? "success" : status.includes("REJECTED") || status === "WITHDRAWN" ? "danger" : "secondary"}
              disabled={busy}
              onClick={() => handleTransition(status)}
            >
              {status.replace(/_/g, " ")}
            </Button>
          ))}
          {options.length === 0 ? <span className="text-xs text-gray-400">Terminal</span> : null}
        </div>
      </td>
    </tr>
  );
}

export default function SubmissionsScreen() {
  const [demandId, setDemandId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [submissions, setSubmissions] = useState([]);
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [subsRes, violRes] = await Promise.all([getSubmissions(), getSubmissionViolations()]);
      setSubmissions(subsRes?.submissions || []);
      setViolations(violRes?.violations || []);
    } catch (err) {
      setError(err.message || "Failed to load submissions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSubmit = async () => {
    if (!demandId.trim() || !candidateId.trim()) {
      setError("Demand ID and Candidate ID are both required.");
      return;
    }
    setError("");
    setNotice("");
    try {
      await submitCandidate({ demandId: demandId.trim(), candidateId: candidateId.trim() });
      setNotice("Candidate submitted.");
      setCandidateId("");
      await load();
    } catch (err) {
      // client.js's formatApiErrorMessage() already joins the backend's
      // array-of-blockers 422 detail into one readable string.
      setError(err.message || "Submission blocked.");
    }
  };

  return (
    <div className="grid gap-4">
      <Card
        title="Client Submissions"
        subtitle="Submit a candidate to a demand -- experience, market-profile (employee status), and employment-type compliance gates all run before it's created."
        icon={<Send className="h-4 w-4" />}
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
        {notice ? (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Demand ID" value={demandId} onChange={setDemandId} placeholder="demand UUID" />
          <Input label="Candidate ID" value={candidateId} onChange={setCandidateId} placeholder="candidate ID" />
        </div>
        <div className="mt-3">
          <Button variant="primary" onClick={handleSubmit}>
            <Send className="h-4 w-4" /> Submit Candidate
          </Button>
        </div>

        <div className="mt-5 overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Candidate / Demand</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Status</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Client Response</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-500">Loading…</td>
                </tr>
              ) : submissions.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-sm text-gray-500">No submissions yet.</td>
                </tr>
              ) : (
                submissions.map((s) => <SubmissionRow key={s.id} submission={s} onChanged={load} />)
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {violations.length > 0 ? (
        <Card
          title="Compliance Violation Log"
          subtitle="Every blocked submission attempt -- audit trail, no exceptions."
          icon={<AlertTriangle className="h-4 w-4" />}
        >
          <ul className="space-y-2 text-xs text-gray-700">
            {violations.map((v) => (
              <li key={v.id} className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2">
                <span className="font-semibold">{v.violation_type}</span> — {v.blocked_message}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
