// Job kinds review (CEO 2026-11-27): a job is either a hiring requisition (Recruitment: BlitzenX hires people as
// employees) or a client role (Workforce: filled only by bench employees). Existing jobs were classified from their
// records; the ones whose records disagree are listed here, read-only until an administrator picks their kind.
import { useCallback, useEffect, useState } from "react";
import { Card } from "../components/ui";
import { classifyJob, getJobsToClassify } from "../services/api/jobKinds";

function JobRow({ job, onDone }) {
  const [kind, setKind] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await classifyJob(job.job_id, kind, reason);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-b align-top">
      <td className="px-2 py-2">
        <div className="font-medium text-gray-900">{job.title}</div>
        <div className="text-xs text-gray-500">{job.company || "No company"} · {job.job_id}</div>
      </td>
      <td className="px-2 py-2 text-xs text-gray-600">{job.evidence}</td>
      <td className="px-2 py-2">
        <select className="w-full rounded-lg border px-2 py-1.5 text-sm" value={kind} disabled={busy}
          onChange={(e) => setKind(e.target.value)}>
          <option value="">Pick the kind</option>
          <option value="REQUISITION">Hiring requisition (internal)</option>
          <option value="CLIENT_DEMAND">Client role</option>
        </select>
        <input className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" placeholder="Why (kept with it)"
          value={reason} disabled={busy} onChange={(e) => setReason(e.target.value)} />
        {error ? <div className="mt-1 text-xs text-rose-700">{error}</div> : null}
        <button type="button" disabled={busy || !kind || !reason.trim()} onClick={save}
          className="mt-1 rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">
          Save
        </button>
      </td>
    </tr>
  );
}

export default function JobKindsReviewScreen() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJobsToClassify();
      setJobs(data.jobs || []);
      setError("");
    } catch (err) {
      setError(`Could not load the jobs to classify: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card title="Job kinds" subtitle={`Jobs whose records disagree on whether they are an internal hiring requisition or a client role. They can't be changed until classified. ${jobs.length} to review.`}>
      <div className="px-5 py-4">
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500">
              <th className="px-2 py-2">Job</th>
              <th className="px-2 py-2">What the records say</th>
              <th className="w-72 px-2 py-2">Kind</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => <JobRow key={job.job_id} job={job} onDone={load} />)}
            {!loading && !jobs.length ? (
              <tr><td colSpan={3} className="px-2 py-8 text-center text-sm text-gray-500">Every job is classified.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
