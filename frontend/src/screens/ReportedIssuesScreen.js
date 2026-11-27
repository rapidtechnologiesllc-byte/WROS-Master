// Reported issues (CEO 2026-11-27): every issue reported from Ask Flash -> Report an Issue, tracked in HRMS until it
// is fixed. Laid out like an issue log (key, summary, type, priority, status, reporter, assignee, created / updated);
// each issue opens with its description and a comment thread (status and assignee changes appear in it too).
import { useCallback, useEffect, useState } from "react";
import { Card } from "../components/ui";
import {
  commentOnReportedIssue, getReportedIssue, listReportedIssues, updateReportedIssue,
} from "../services/api/defects";
import { getUserDirectory } from "../services/api/users";
import { hasPermission } from "../utils/permissionsRoleTemplate";
import cx from "../utils/cx";

const STATUS_LABELS = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  FIXED: "Fixed",
  WONT_FIX: "Will not fix",
  DUPLICATE: "Duplicate",
};
const STATUS_STYLES = {
  OPEN: "bg-rose-100 text-rose-800",
  IN_PROGRESS: "bg-amber-100 text-amber-800",
  FIXED: "bg-emerald-100 text-emerald-800",
  WONT_FIX: "bg-gray-100 text-gray-700",
  DUPLICATE: "bg-gray-100 text-gray-700",
};
const PRIORITY_STYLES = {
  CRITICAL: "text-red-700 font-semibold",
  HIGH: "text-orange-700 font-semibold",
  MEDIUM: "text-gray-800",
  LOW: "text-gray-500",
};
const CLOSED = ["FIXED", "WONT_FIX", "DUPLICATE"];

const when = (iso) => (iso ? new Date(iso).toLocaleString() : "-");

function IssueDetail({ issueId, people, onChanged, onClose }) {
  const [issue, setIssue] = useState(null);
  const [comment, setComment] = useState("");
  const [resolution, setResolution] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canEdit = hasPermission("error-logs", "edit");

  const load = useCallback(async () => {
    try {
      const data = await getReportedIssue(issueId);
      setIssue(data);
      setResolution(data.resolution || "");
    } catch (err) {
      setError(`Could not open the issue: ${err.message}`);
    }
  }, [issueId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (action) => {
    setBusy(true);
    setError("");
    try {
      const data = await action();
      if (data?.comments) {
        setIssue(data);
      } else {
        await load();
      }
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!issue) {
    return <div className="p-4 text-sm text-gray-500">{error || "Loading..."}</div>;
  }
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-gray-500">{issue.reference} · {issue.issue_type} · {issue.screen}</div>
          <h3 className="text-base font-semibold text-gray-900">{issue.summary}</h3>
        </div>
        <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-800">Close</button>
      </div>
      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <div>
          <div className="text-gray-500">Status</div>
          <span className={cx("rounded px-2 py-0.5", STATUS_STYLES[issue.status])}>{STATUS_LABELS[issue.status]}</span>
        </div>
        <div>
          <div className="text-gray-500">Priority</div>
          <span className={PRIORITY_STYLES[issue.severity]}>{issue.severity}{issue.blocking ? " · blocking" : ""}</span>
        </div>
        <div><div className="text-gray-500">Reporter</div>{issue.reporter_name || "-"}</div>
        <div><div className="text-gray-500">Reported</div>{when(issue.created_at)}</div>
      </div>
      <div>
        <div className="mb-1 text-xs font-semibold text-gray-700">Description</div>
        <p className="whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-800">{issue.description}</p>
      </div>
      {canEdit ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-xs text-gray-700">
            Assignee
            <select
              className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm"
              disabled={busy}
              value={issue.assignee_user_id || ""}
              onChange={(e) => run(() => updateReportedIssue(issue.id, { assignee_user_id: e.target.value }))}
            >
              <option value="">Unassigned</option>
              {people.map((p) => <option key={p.user_id} value={p.user_id}>{p.user_name}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-700">
            Status
            <select
              className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm"
              disabled={busy}
              value={issue.status}
              onChange={(e) => run(() => updateReportedIssue(issue.id, { status: e.target.value, resolution }))}
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-700 sm:col-span-2">
            Resolution: what was done (or why not) and where (PR or commit). Needed to close the issue.
            <textarea
              className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm"
              rows={2}
              value={resolution}
              disabled={busy}
              onChange={(e) => setResolution(e.target.value)}
              onBlur={() => {
                if (resolution !== (issue.resolution || "")) run(() => updateReportedIssue(issue.id, { resolution }));
              }}
            />
          </label>
        </div>
      ) : issue.resolution ? (
        <div className="text-xs text-gray-700"><span className="font-semibold">Resolution:</span> {issue.resolution}</div>
      ) : null}
      <div>
        <div className="mb-2 text-xs font-semibold text-gray-700">Activity</div>
        <ul className="space-y-2">
          {(issue.comments || []).map((c) => (
            <li
              key={c.id}
              className={cx("rounded-lg border px-3 py-2 text-sm", c.kind === "CHANGE" ? "bg-gray-50 text-gray-600" : "bg-white")}
            >
              <div className="text-xs text-gray-500">{c.author_name || "System"} · {when(c.created_at)}</div>
              <div className="whitespace-pre-wrap">{c.body}</div>
            </li>
          ))}
          {!issue.comments?.length ? <li className="text-xs text-gray-500">No comments yet.</li> : null}
        </ul>
        <div className="mt-2 flex gap-2">
          <textarea
            className="flex-1 rounded-lg border px-2 py-1.5 text-sm"
            rows={2}
            placeholder="Add a comment..."
            value={comment}
            disabled={busy}
            onChange={(e) => setComment(e.target.value)}
          />
          <button
            type="button"
            disabled={busy || !comment.trim()}
            className="self-end rounded-lg bg-gray-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
            onClick={() => run(async () => {
              const data = await commentOnReportedIssue(issue.id, comment);
              setComment("");
              return data;
            })}
          >
            Comment
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ReportedIssuesScreen() {
  const [issues, setIssues] = useState([]);
  const [openCount, setOpenCount] = useState(0);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [people, setPeople] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listReportedIssues(filter);
      setIssues(data.issues || []);
      setOpenCount(data.open_count || 0);
      setError("");
    } catch (err) {
      setError(`Could not load the reported issues: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!hasPermission("error-logs", "edit")) return;
    getUserDirectory()
      .then((data) => setPeople((data?.users || []).filter((u) => u.active !== false)))
      .catch((err) => setError(`Could not load people to assign: ${err.message}`));
  }, []);

  return (
    <Card title="Reported issues" subtitle={`Every issue reported from the app, tracked until it is fixed. ${openCount} open.`}>
      <div className="px-5 py-4">
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}
        <select
          className="mb-3 w-52 rounded-lg border px-2 py-1.5 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">All issues</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-500">
                <th className="px-2 py-2">Key</th>
                <th className="px-2 py-2">Summary</th>
                <th className="px-2 py-2">Type</th>
                <th className="px-2 py-2">Priority</th>
                <th className="px-2 py-2">Status</th>
                <th className="px-2 py-2">Reporter</th>
                <th className="px-2 py-2">Assignee</th>
                <th className="px-2 py-2">Created</th>
                <th className="px-2 py-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i) => (
                <tr
                  key={i.id}
                  onClick={() => setSelected(i.id)}
                  className={cx(
                    "cursor-pointer border-b hover:bg-gray-50",
                    selected === i.id && "bg-orange-50",
                    CLOSED.includes(i.status) && "text-gray-500",
                  )}
                >
                  <td className="whitespace-nowrap px-2 py-2 text-xs">{i.reference}</td>
                  <td className="min-w-[18rem] px-2 py-2">
                    <div className="font-medium text-gray-900">{i.summary}</div>
                    <div className="text-xs text-gray-500">{i.screen}</div>
                  </td>
                  <td className="px-2 py-2 text-xs">{i.issue_type}</td>
                  <td className={cx("px-2 py-2 text-xs", PRIORITY_STYLES[i.severity])}>{i.severity}{i.blocking ? " · blocking" : ""}</td>
                  <td className="px-2 py-2">
                    <span className={cx("rounded px-2 py-0.5 text-xs", STATUS_STYLES[i.status])}>{STATUS_LABELS[i.status]}</span>
                  </td>
                  <td className="px-2 py-2 text-xs">{i.reporter_name || "-"}</td>
                  <td className="px-2 py-2 text-xs">{i.assignee_name || "Unassigned"}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-xs">{when(i.created_at)}</td>
                  <td className="whitespace-nowrap px-2 py-2 text-xs">{when(i.updated_at)}</td>
                </tr>
              ))}
              {!loading && !issues.length ? (
                <tr><td colSpan={9} className="px-2 py-8 text-center text-sm text-gray-500">No reported issues.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {selected ? (
          <div className="mt-4 rounded-xl border">
            <IssueDetail issueId={selected} people={people} onChanged={load} onClose={() => setSelected(null)} />
          </div>
        ) : null}
      </div>
    </Card>
  );
}
