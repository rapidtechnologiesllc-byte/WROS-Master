// Hiring Analytics (a tab of the Recruitment Dashboard): where hires come from, what became of each
// recruiter's candidates, and open positions against people who joined. Every number is read from the
// hiring pipeline's stages, so it agrees with the candidate pages; the reader sees their own scope.
import { useCallback, useEffect, useState } from "react";
import { BarChart3, RefreshCw } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import { getHiringAnalytics } from "../services/api/thunderAnalytics";

const FUNNEL_COLUMNS = [
  ["added", "Added"],
  ["interviewed", "Interviewed"],
  ["offered", "Offered"],
  ["accepted", "Accepted"],
  ["hired", "Joined"],
  ["rejected", "Rejected"],
];

function isoDaysAgo(days) {
  const day = new Date();
  day.setDate(day.getDate() - days);
  return day.toISOString().slice(0, 10);
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-2xl border bg-white px-4 py-3 dark:bg-gray-800">
      <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">{label}</div>
      <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</div>
      {note ? <div className="text-xs text-gray-500 dark:text-gray-400">{note}</div> : null}
    </div>
  );
}

function FunnelTable({ firstColumn, rows, empty }) {
  if (!rows.length) return <div className="text-sm text-gray-600 dark:text-gray-300">{empty}</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-xs font-semibold text-gray-500 dark:text-gray-400">
            <th className="py-2 pr-3">{firstColumn}</th>
            {FUNNEL_COLUMNS.map(([key, label]) => (
              <th key={key} className="px-3 py-2 text-right">{label}</th>
            ))}
            <th className="px-3 py-2 text-right">Joined of added</th>
            <th className="py-2 pl-3 text-right">Days to offer</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.recruiter_id || row.label} className="border-b last:border-0">
              <td className="py-2 pr-3 font-semibold text-gray-900 dark:text-gray-100">{row.label}</td>
              {FUNNEL_COLUMNS.map(([key]) => (
                <td key={key} className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">{row[key]}</td>
              ))}
              <td className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">
                {row.hire_rate_pct == null ? "—" : `${row.hire_rate_pct}%`}
              </td>
              <td className="py-2 pl-3 text-right text-gray-800 dark:text-gray-200">
                {row.avg_days_to_offer == null ? "—" : row.avg_days_to_offer}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function HiringAnalyticsScreen() {
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(90));
  const [dateTo, setDateTo] = useState(isoDaysAgo(0));
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (from, to) => {
    setLoading(true);
    setError("");
    try {
      setReport(await getHiringAnalytics({ dateFrom: from, dateTo: to }));
    } catch (err) {
      setError(err.message || "Could not load hiring analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(isoDaysAgo(90), isoDaysAgo(0));
  }, [load]);

  const totals = report ? report.totals : null;
  const positions = report ? report.position_totals : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Input label="Candidates added from" type="date" value={dateFrom} onChange={setDateFrom} />
        </div>
        <div className="w-44">
          <Input label="to" type="date" value={dateTo} onChange={setDateTo} />
        </div>
        <Button variant="primary" disabled={loading || !dateFrom || !dateTo} onClick={() => load(dateFrom, dateTo)}>
          <RefreshCw className="h-4 w-4" /> {loading ? "Loading…" : "Show"}
        </Button>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      ) : null}

      {report ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Candidates added" value={totals.added} note={`${report.date_from} to ${report.date_to}`} />
            <Stat label="Reached an interview" value={totals.interviewed} />
            <Stat
              label="Joined"
              value={totals.hired}
              note={totals.hire_rate_pct == null ? null : `${totals.hire_rate_pct}% of those added`}
            />
            <Stat
              label="Positions still to hire"
              value={positions.still_to_hire}
              note={`${positions.positions} open position(s), ${positions.hired} joined`}
            />
          </div>

          <Card
            title="Source of hire"
            subtitle="Candidates added in the period by where they came from, and how far they got"
            icon={<BarChart3 className="h-4 w-4" />}
          >
            <FunnelTable firstColumn="Source" rows={report.sources} empty="No candidates were added in this period." />
          </Card>

          <Card title="Recruiters" subtitle="The same candidates by their recruiter">
            <FunnelTable firstColumn="Recruiter" rows={report.recruiters} empty="No candidates were added in this period." />
          </Card>

          <Card
            title="Open positions against hires"
            subtitle="Every open job today, whatever the period: positions asked for, people who joined, and who is on the way"
          >
            {report.positions.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-xs font-semibold text-gray-500 dark:text-gray-400">
                      <th className="py-2 pr-3">Job</th>
                      <th className="px-3 py-2 text-right">Positions</th>
                      <th className="px-3 py-2 text-right">Joined</th>
                      <th className="px-3 py-2 text-right">Offers out</th>
                      <th className="px-3 py-2 text-right">In interviews</th>
                      <th className="py-2 pl-3 text-right">Still to hire</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.positions.map((job) => (
                      <tr key={job.job_id} className="border-b last:border-0">
                        <td className="py-2 pr-3">
                          <div className="font-semibold text-gray-900 dark:text-gray-100">{job.title || "(untitled job)"}</div>
                          {job.opened_on ? <div className="text-xs text-gray-500">opened {job.opened_on}</div> : null}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">{job.positions}</td>
                        <td className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">{job.hired}</td>
                        <td className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">{job.offers_out}</td>
                        <td className="px-3 py-2 text-right text-gray-800 dark:text-gray-200">{job.in_progress}</td>
                        <td className="py-2 pl-3 text-right font-semibold text-gray-900 dark:text-gray-100">{job.still_to_hire}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-gray-600 dark:text-gray-300">There are no open jobs.</div>
            )}
          </Card>
        </>
      ) : null}
      {loading && !report ? <div className="text-sm text-gray-500">Loading…</div> : null}
    </div>
  );
}
