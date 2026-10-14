// Submissions, two tabs (CEO 2026-10-14):
// - External: bench employees submitted to a client, Core (direct client) or Staff Aug. The
//   pickers come from GET /submissions/options; the selected pair is checked by GET
//   /submissions/readiness, the same gates POST /submissions enforces.
// - Internal: market candidates put on a job, moving through the hiring pipeline to the bench.
// Statuses, their labels and the allowed next responses all come from the API.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Send, RefreshCw, AlertTriangle, Users } from "lucide-react";
import { Card, Button, Select } from "../components/ui";
import cx from "../utils/cx";
import {
  submitCandidate,
  getSubmissions,
  getInternalSubmissions,
  getSubmissionOptions,
  getSubmissionReadiness,
  getSubmissionViolations,
  recordClientResponse,
} from "../services/api/submissions";

const jobLabel = (job) =>
  `${job.client_name} — ${job.job_title}${job.delivery_line_label ? ` · ${job.delivery_line_label}` : ""}`;

const candidateLabel = (candidate) =>
  [candidate.name, candidate.employee_status, ...(candidate.issues || [])].join(" · ");

const CandidateLink = ({ id, name }) => (
  <Link to={`/candidates/${encodeURIComponent(id)}`} className="font-semibold text-blue-700 hover:underline">
    {name}
  </Link>
);

const Th = ({ children }) => <th className="px-4 py-3 text-xs font-semibold text-gray-700">{children}</th>;

function TableState({ loading, empty, colSpan, emptyText }) {
  if (!loading && !empty) return null;
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-8 text-center text-sm text-gray-500">
        {loading ? "Loading…" : emptyText}
      </td>
    </tr>
  );
}

function ExternalRow({ submission, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const next = submission.next_statuses || [];

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
      <td className="px-4 py-3">
        <CandidateLink id={submission.candidate_id} name={submission.candidate_name} />
        <div className="text-xs text-gray-500">Employee: {submission.employee_status || "—"}</div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-700">
        <div className="font-semibold text-gray-900">{submission.client_name || "—"}</div>
        {submission.demand_job_title}
      </td>
      <td className="px-4 py-3 text-xs text-gray-700">{submission.delivery_line_label || "Not set"}</td>
      <td className="px-4 py-3 text-xs font-semibold text-gray-800">{submission.status_label}</td>
      <td className="px-4 py-3">
        {error ? <div className="mb-1 text-xs text-rose-700">{error}</div> : null}
        <div className="flex flex-wrap gap-1">
          {next.map((option) => (
            <Button
              key={option.value}
              variant={
                option.value === "PLACED"
                  ? "success"
                  : ["REJECTED_BY_CLIENT", "WITHDRAWN"].includes(option.value)
                    ? "danger"
                    : "secondary"
              }
              disabled={busy}
              onClick={() => handleTransition(option.value)}
            >
              {option.label}
            </Button>
          ))}
          {next.length === 0 ? <span className="text-xs text-gray-400">Closed</span> : null}
        </div>
      </td>
    </tr>
  );
}

function ExternalTab({ loading, submissions, options, onChanged }) {
  const [demandId, setDemandId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [readiness, setReadiness] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // the selected pair is checked against every gate before the button is enabled
  useEffect(() => {
    let live = true;
    setReadiness(null);
    setError("");
    if (!demandId || !candidateId) return undefined;
    getSubmissionReadiness(candidateId, demandId)
      .then((r) => live && setReadiness(r))
      .catch((err) => live && setError(err.message || "Could not check the candidate."));
    return () => {
      live = false;
    };
  }, [demandId, candidateId]);

  const jobOptions = [{ value: "", label: options.jobs.length ? "Select a client job" : "No open client jobs" }]
    .concat(options.jobs.map((j) => ({ value: j.id, label: jobLabel(j) })));
  const candidateOptions = [
    { value: "", label: options.candidates.length ? "Select a bench employee" : "No bench employees" },
  ].concat(options.candidates.map((c) => ({ value: c.id, label: candidateLabel(c) })));
  const canSubmit = readiness?.action === "SUBMIT_TO_CLIENT";

  const handleSubmit = async () => {
    setError("");
    setNotice("");
    try {
      await submitCandidate({ demandId, candidateId });
      setNotice("Submitted to the client.");
      setCandidateId("");
      await onChanged();
    } catch (err) {
      // apiRequest already joins every blocker the backend returned into the message
      setError(err.message || "Submission blocked.");
    }
  };

  return (
    <>
      {error ? (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      ) : null}
      {notice ? (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Select label="Client job" value={demandId} onChange={setDemandId} options={jobOptions} disabled={loading} />
        <Select label="Candidate" value={candidateId} onChange={setCandidateId} options={candidateOptions} disabled={loading} />
      </div>
      {readiness && !canSubmit ? (
        <ul className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {readiness.blockers.map((b) => (
            <li key={b.error + b.message}>{b.message}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-3">
        <Button variant="primary" onClick={handleSubmit} disabled={loading || !canSubmit}>
          <Send className="h-4 w-4" /> Submit to Client
        </Button>
      </div>

      <div className="mt-5 overflow-visible rounded-2xl border">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50">
            <tr>
              <Th>Candidate</Th>
              <Th>Client / Job</Th>
              <Th>Type</Th>
              <Th>Status</Th>
              <Th>Client Response</Th>
            </tr>
          </thead>
          <tbody className="divide-y bg-white">
            <TableState loading={loading} empty={!submissions.length} colSpan={5} emptyText="No client submissions yet." />
            {!loading && submissions.map((s) => <ExternalRow key={s.id} submission={s} onChanged={onChanged} />)}
          </tbody>
        </table>
      </div>
    </>
  );
}

function InternalTab({ loading, rows }) {
  return (
    <div className="overflow-visible rounded-2xl border">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50">
          <tr>
            <Th>Candidate</Th>
            <Th>Client / Job</Th>
            <Th>Type</Th>
            <Th>Hiring Stage</Th>
            <Th>Next Step Blocked By</Th>
          </tr>
        </thead>
        <tbody className="divide-y bg-white">
          <TableState loading={loading} empty={!rows.length} colSpan={5} emptyText="No candidates on jobs yet." />
          {!loading &&
            rows.map((r) => (
              <tr key={r.application_id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <CandidateLink id={r.candidate_id} name={r.candidate_name} />
                  <div className="text-xs text-gray-500">
                    Applied {r.applied_at ? new Date(r.applied_at).toLocaleDateString() : "—"}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-700">
                  <div className="font-semibold text-gray-900">{r.client_name || "—"}</div>
                  {r.job_title}
                </td>
                <td className="px-4 py-3 text-xs text-gray-700">{r.delivery_line_label || "Not set"}</td>
                <td className="px-4 py-3 text-xs font-semibold text-gray-800">{(r.stage || "").replace(/_/g, " ")}</td>
                <td className="px-4 py-3 text-xs text-gray-600">{(r.blockers || []).join("; ") || "—"}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SubmissionsScreen() {
  const [tab, setTab] = useState("external");
  const [submissions, setSubmissions] = useState([]);
  const [internal, setInternal] = useState([]);
  const [violations, setViolations] = useState([]);
  const [options, setOptions] = useState({ jobs: [], candidates: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    // settled, not all: one failing call must not blank the others
    const results = await Promise.allSettled([
      getSubmissions(),
      getInternalSubmissions(),
      getSubmissionOptions(),
      getSubmissionViolations(),
    ]);
    const [subsRes, internalRes, optionsRes, violRes] = results;
    if (subsRes.status === "fulfilled") setSubmissions(subsRes.value?.submissions || []);
    if (internalRes.status === "fulfilled") setInternal(internalRes.value?.submissions || []);
    if (optionsRes.status === "fulfilled") {
      setOptions({ jobs: optionsRes.value?.jobs || [], candidates: optionsRes.value?.candidates || [] });
    }
    if (violRes.status === "fulfilled") setViolations(violRes.value?.violations || []);
    const failed = results.filter((r) => r.status === "rejected");
    if (failed.length) setError(failed.map((r) => r.reason?.message || "Request failed.").join(" "));
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const tabs = useMemo(
    () => [
      { key: "external", label: `External (${submissions.length})`, icon: <Send className="h-4 w-4" /> },
      { key: "internal", label: `Internal (${internal.length})`, icon: <Users className="h-4 w-4" /> },
    ],
    [submissions.length, internal.length],
  );

  return (
    <div className="grid gap-4">
      <Card
        title="Submissions"
        subtitle={
          tab === "external"
            ? "Bench employees to a client: Core (direct client) needs Core certification; both models need Buddy graduated, no open escalation, 5+ years and the job's minimum."
            : "Market candidates on jobs, on their way to the bench: Screen → L1 → L2 → Offer → Onboarding → BGV → Bench."
        }
        icon={<Send className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        <div className="mb-4 flex gap-2 border-b">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cx(
                "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-semibold",
                tab === t.key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-800",
              )}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        {tab === "external" ? (
          <ExternalTab loading={loading} submissions={submissions} options={options} onChanged={load} />
        ) : (
          <InternalTab loading={loading} rows={internal} />
        )}
      </Card>

      {tab === "external" && violations.length > 0 ? (
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
