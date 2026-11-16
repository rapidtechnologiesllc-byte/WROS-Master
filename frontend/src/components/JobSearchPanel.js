// A job's boolean search (open requirements P906/P907, CEO 2026-11-16): the search the recruiter agent runs for the
// job, written by the system from the job's skills and editable by a recruiter (who can go back to the system's
// version), and the candidates it captured: where each word was found and what the agent did about each.
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, TextArea, Table } from "./ui";
import { BooleanSearchHelp, FoundWhere } from "./BooleanSearchHelp";
import {
  getJobSearchCriteria, listJobSearchMatches, resetJobSearchCriteria, runJobSearchNow, saveJobSearchCriteria,
} from "../services/api/jobSearch";
import { hasPermission } from "../utils/permissionsRoleTemplate";

const STATUS_LABELS = { CAPTURED: "Found", CONTACTED: "Written to", SKIPPED: "Not written to" };
const when = (value) => (value ? new Date(value).toLocaleString() : "—");

export default function JobSearchPanel({ jobId }) {
  const [criteria, setCriteria] = useState(null);
  const [matches, setMatches] = useState([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canEdit = hasPermission("jobs", "edit");

  const load = useCallback(async () => {
    try {
      const [loaded, found] = await Promise.all([getJobSearchCriteria(jobId), listJobSearchMatches(jobId)]);
      setCriteria(loaded);
      setQuery(loaded.query);
      setMatches(found?.matches || []);
      setError("");
    } catch (err) {
      console.error(`[JobSearchPanel] Failed to load the search for ${jobId}:`, err);
      setError(`Couldn't load this job's search: ${err.message}`);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (label, call, done) => {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      const result = await call();
      setNotice(done(result));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  if (!criteria) {
    return <div className="rounded-2xl border bg-white p-6 text-sm text-gray-500 shadow-sm">{error || "Loading…"}</div>;
  }

  const changed = query.trim() !== criteria.query;
  const rows = matches.map((m) => ({
    id: m.candidate_id,
    name: <Link className="font-semibold text-blue-600 hover:underline" to={`/candidates/${m.candidate_id}`}>{m.name}</Link>,
    title: m.title || "—",
    location: m.location || "—",
    experience: m.experience_years != null ? `${m.experience_years} yrs` : "—",
    score: m.score,
    found: (
      <div>
        <FoundWhere found={m.found} />
        {m.snippet ? <div className="mt-1 max-w-md text-xs italic text-gray-500">{m.snippet}</div> : null}
      </div>
    ),
    status: (
      <div className="text-xs">
        <div className="font-semibold">{STATUS_LABELS[m.status] || m.status}</div>
        {m.note ? <div className="text-gray-500">{m.note}</div> : null}
        {m.contacted_at ? <div className="text-gray-500">{when(m.contacted_at)}</div> : null}
      </div>
    ),
  }));

  return (
    <div className="space-y-3">
      <div className="space-y-3 rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-semibold text-gray-900">Boolean search for this job</div>
          <div className="text-xs text-gray-500">
            {criteria.edited ? `Edited by ${criteria.edited_by_name || "a recruiter"} ${when(criteria.edited_at)}` : "Written by the system from the job's skills"}
            {" · "}Last run {when(criteria.last_run_at)}
          </div>
        </div>
        {error ? <div className="text-xs text-rose-700">{error}</div> : null}
        {notice ? <div className="text-xs text-emerald-700">{notice}</div> : null}
        <TextArea label="Search" value={query} onChange={setQuery} rows={3} disabled={!canEdit} />
        <BooleanSearchHelp />
        {criteria.edited ? (
          <div className="text-xs text-gray-500">The system's version: <code className="rounded bg-gray-100 px-1">{criteria.generated_query}</code></div>
        ) : null}
        {canEdit ? (
          <div className="flex flex-wrap gap-2">
            <Button disabled={!changed || !!busy || !query.trim()}
              onClick={() => act("save", () => saveJobSearchCriteria(jobId, query.trim()), () => "Search saved: it is used from the next run.")}>
              {busy === "save" ? "Saving…" : "Save search"}
            </Button>
            {criteria.edited ? (
              <Button variant="secondary" disabled={!!busy}
                onClick={() => act("reset", () => resetJobSearchCriteria(jobId), () => "Back to the system's version.")}>
                Use the system's version
              </Button>
            ) : null}
            <Button variant="secondary" disabled={!!busy || changed}
              title={changed ? "Save the search first" : undefined}
              onClick={() => act("run", () => runJobSearchNow(jobId),
                (r) => `${r.captured} new candidate${r.captured === 1 ? "" : "s"} found${r.emails_queued ? `, ${r.emails_queued} written to` : ""}.`)}>
              {busy === "run" ? "Searching…" : "Run search now"}
            </Button>
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="mb-2 flex flex-wrap gap-3 text-xs text-gray-600">
          <span className="font-semibold text-gray-900">Candidates found by this search</span>
          <span>{criteria.matches.total} in all</span>
          <span>{criteria.matches.captured} found</span>
          <span>{criteria.matches.contacted} written to</span>
          <span>{criteria.matches.skipped} not written to</span>
        </div>
        <Table
          columns={[
            { key: "name", header: "Candidate" },
            { key: "title", header: "Title" },
            { key: "location", header: "Location" },
            { key: "experience", header: "Experience" },
            { key: "score", header: "Score" },
            { key: "found", header: "Where it matched" },
            { key: "status", header: "What happened" },
          ]}
          rows={rows}
        />
        {!rows.length ? <div className="py-4 text-center text-sm text-gray-500">Nobody found yet: run the search.</div> : null}
      </div>
    </div>
  );
}
