// HRMS-0711 Client Submission Pipeline: submit a bench employee to an open
// client job. The pickers come from GET /submissions/options (scoped like the
// list); every compliance gate still runs on POST /submissions.
import { useEffect, useMemo, useState } from "react";
import { Send, RefreshCw, AlertTriangle } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import cx from "../utils/cx";
import {
  submitCandidate,
  getSubmissions,
  getSubmissionOptions,
  getSubmissionViolations,
  recordClientResponse,
} from "../services/api/submissions";

const jobLabel = (job) => `${job.client_name} — ${job.job_title} (${job.status.replace(/_/g, " ")})`;

const candidateLabel = (candidate, job) => {
  const notes = [candidate.employee_status, ...(candidate.issues || [])];
  // a candidate already submitted by one business unit can't be submitted by another
  if (job?.business_unit_id && candidate.submission_bu_id && candidate.submission_bu_id !== job.business_unit_id) {
    notes.push("locked to another business unit");
  }
  return `${candidate.name} — ${notes.join(" · ")}`;
};

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
        <div className="text-xs text-gray-500">
          → {submission.client_name ? `${submission.client_name} — ` : ""}
          {submission.demand_job_title}
        </div>
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
  const [options, setOptions] = useState({ jobs: [], candidates: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    // settled, not all: one failing call must not blank the others
    const [subsRes, optionsRes, violRes] = await Promise.allSettled([
      getSubmissions(),
      getSubmissionOptions(),
      getSubmissionViolations(),
    ]);
    if (subsRes.status === "fulfilled") setSubmissions(subsRes.value?.submissions || []);
    if (optionsRes.status === "fulfilled") {
      setOptions({ jobs: optionsRes.value?.jobs || [], candidates: optionsRes.value?.candidates || [] });
    }
    if (violRes.status === "fulfilled") setViolations(violRes.value?.violations || []);
    const failed = [subsRes, optionsRes, violRes].filter((r) => r.status === "rejected");
    if (failed.length) {
      setError(failed.map((r) => r.reason?.message || "Request failed.").join(" "));
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const selectedJob = useMemo(() => options.jobs.find((j) => j.id === demandId), [options.jobs, demandId]);
  const jobOptions = [{ value: "", label: options.jobs.length ? "Select a client job" : "No open client jobs" }]
    .concat(options.jobs.map((j) => ({ value: j.id, label: jobLabel(j) })));
  const candidateOptions = [
    { value: "", label: options.candidates.length ? "Select a bench employee" : "No bench employees" },
  ].concat(options.candidates.map((c) => ({ value: c.id, label: candidateLabel(c, selectedJob) })));

  const handleSubmit = async () => {
    if (!demandId || !candidateId) {
      setError("Select a client job and a candidate.");
      return;
    }
    setError("");
    setNotice("");
    try {
      await submitCandidate({ demandId, candidateId });
      setNotice("Candidate submitted to the client.");
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
        subtitle="Submit a bench employee to an open client job. The 5-year experience, employee-status, W2, background-check and hiring-pipeline gates all run before it's created."
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
          <Select label="Client job" value={demandId} onChange={setDemandId} options={jobOptions} disabled={loading} />
          <Select
            label="Candidate"
            value={candidateId}
            onChange={setCandidateId}
            options={candidateOptions}
            disabled={loading}
          />
        </div>
        <div className="mt-3">
          <Button variant="primary" onClick={handleSubmit} disabled={loading || !demandId || !candidateId}>
            <Send className="h-4 w-4" /> Submit Candidate
          </Button>
        </div>

        <div className="mt-5 overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Candidate / Client Job</th>
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
