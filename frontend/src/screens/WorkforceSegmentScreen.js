// One Workforce Overview number on its own page: the people in one group
// (/workforce/:groupSlug) or with one flag (/workforce/flags/:flagSlug). The count shown is the
// same number the dashboard linked from.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import {
  flagKeyFromSlug, getWorkforceSelection, groupKeyFromSlug, groupPath, isBenchGroup, toSlug, BENCH_PATH,
} from "../services/api/workforce";

const Th = ({ children }) => <th className="px-4 py-3 text-xs font-semibold text-gray-700">{children}</th>;

function Flags({ person, windowDays }) {
  const flags = [];
  if (person.rolling_off) flags.push(`Rolling off (≤${windowDays}d)`);
  if (person.open_escalations) flags.push(`${person.open_escalations} open escalation(s)`);
  if (person.notice_period) flags.push("Notice period");
  if (!flags.length) return <span className="text-gray-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {flags.map((f) => (
        <span key={f} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">{f}</span>
      ))}
    </div>
  );
}

export default function WorkforceSegmentScreen() {
  const { groupSlug, flagSlug } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getWorkforceSelection(flagSlug ? { flag: flagKeyFromSlug(flagSlug) } : { group: groupKeyFromSlug(groupSlug) }));
    } catch (err) {
      setData(null);
      setError(err.message || "Failed to load this group.");
    } finally {
      setLoading(false);
    }
  }, [groupSlug, flagSlug]);

  // reloads exactly when the URL (the group or flag) changes
  useEffect(() => {
    load();
  }, [load]);

  const selection = data?.selection;
  const siblings = selection?.kind === "flag" ? data?.flags || [] : data?.groups || [];
  const siblingPath = (key) => (selection?.kind === "flag" ? `/workforce/flags/${toSlug(key)}` : groupPath(key));

  // a bench group's page is the bench screen (days, cost and earnings per person)
  if (groupSlug && isBenchGroup(groupKeyFromSlug(groupSlug))) {
    return <Navigate to={`${BENCH_PATH}?group=${groupKeyFromSlug(groupSlug)}`} replace />;
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/workforce" className="flex items-center gap-1 font-semibold text-blue-700 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Workforce Overview
        </Link>
        {siblings.map((s) => (
          <Link
            key={s.key}
            to={siblingPath(s.key)}
            className={cx(
              "rounded-full border px-3 py-1 text-xs font-semibold",
              s.key === selection?.key ? "border-gray-900 bg-gray-900 text-white" : "text-gray-700 hover:border-gray-500",
            )}
          >
            {s.label} ({s.count})
          </Link>
        ))}
      </div>

      <Card
        title={selection ? `${selection.label} (${selection.count})` : "Workforce"}
        subtitle={selection?.description}
        right={
          <Button variant="ghost" onClick={load} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading ? "animate-spin" : "")} /> Refresh
          </Button>
        }
      >
        {error ? (
          <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        <div className="overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <Th>Employee</Th>
                {selection?.kind === "flag" ? <Th>Group</Th> : null}
                <Th>Business Unit</Th>
                <Th>Buddy / Core</Th>
                <Th>Client / Project</Th>
                <Th>Allocation Ends</Th>
                <Th>Flags</Th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading || !selection?.people?.length ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">
                    {loading ? "Loading…" : "Nobody here."}
                  </td>
                </tr>
              ) : (
                selection.people.map((p) => (
                  <tr key={p.employee_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      {p.candidate_id ? (
                        <Link to={`/candidates/${encodeURIComponent(p.candidate_id)}`} className="font-semibold text-blue-700 hover:underline">
                          {p.name}
                        </Link>
                      ) : (
                        <span className="font-semibold">{p.name}</span>
                      )}
                      <div className="text-xs text-gray-500">{p.status.replace(/_/g, " ")}</div>
                    </td>
                    {selection.kind === "flag" ? (
                      <td className="px-4 py-3 text-xs">
                        <Link to={groupPath(p.group)} className="text-blue-700 hover:underline">{p.group_label}</Link>
                      </td>
                    ) : null}
                    <td className="px-4 py-3 text-xs text-gray-700">{p.business_unit || "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      Buddy {p.buddy_program_status.replace(/_/g, " ").toLowerCase()}
                      <div>{p.core_certified ? "Core-certified" : "Not Core-certified"}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      <div className="font-semibold text-gray-900">{p.client || "—"}</div>
                      {p.project || ""}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">{p.allocation_end_date || "—"}</td>
                    <td className="px-4 py-3 text-xs"><Flags person={p} windowDays={data.roll_off_window_days} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
