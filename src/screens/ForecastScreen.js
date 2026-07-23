// S-256/HRMS-0506 (canonical) Resource Demand Planning / Future Demand
// vs Bench Forecast. Read-only reporting -- allocation end dates are
// planning estimates, not contractual commitments (labeled as such).
import { useEffect, useState } from "react";
import { TrendingUp, RefreshCw, Clock3 } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getExpiringAllocations, getSkillGapAnalysis } from "../services/api/resourceForecast";

function ExpiryColumn({ title, tone, items }) {
  return (
    <div className="rounded-2xl border p-3">
      <div className={cx("mb-2 inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold", tone)}>
        <Clock3 className="h-3 w-3" /> {title}
      </div>
      {items.length === 0 ? (
        <div className="py-4 text-center text-xs text-gray-400">None</div>
      ) : (
        <ul className="space-y-2">
          {items.map((e) => (
            <li key={e.allocation_id} className="rounded-lg border px-2.5 py-2 text-xs">
              <div className="font-semibold text-gray-900">{e.employee_name}</div>
              <div className="text-gray-500">{e.skills.join(", ") || "—"}</div>
              <div className="text-gray-400">Ends {e.end_date} ({e.days_out}d)</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ForecastScreen() {
  const [expiring, setExpiring] = useState(null);
  const [gapRows, setGapRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [expiringRes, gapRes] = await Promise.all([getExpiringAllocations(), getSkillGapAnalysis()]);
      setExpiring(expiringRes);
      setGapRows(gapRes?.rows || []);
    } catch (err) {
      setError(err.message || "Failed to load the resource forecast.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="grid gap-4">
      <Card
        title="Resource Demand Planning"
        subtitle="Estimates for planning only, not contractual commitments -- who's coming off allocation soon, and where bench supply is ahead of or behind open demand by skill."
        icon={<TrendingUp className="h-4 w-4" />}
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

        {loading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : (
          <>
            <div className="mb-2 text-sm font-semibold text-gray-700">Expiring Allocations</div>
            <div className="grid gap-3 sm:grid-cols-3">
              <ExpiryColumn
                title="Ending < 30 days"
                tone="border-rose-200 bg-rose-50 text-rose-800"
                items={expiring?.under_30_days || []}
              />
              <ExpiryColumn
                title="30-60 days"
                tone="border-amber-200 bg-amber-50 text-amber-800"
                items={expiring?.thirty_to_60_days || []}
              />
              <ExpiryColumn
                title="60-90 days"
                tone="border-gray-200 bg-gray-50 text-gray-700"
                items={expiring?.sixty_to_90_days || []}
              />
            </div>

            <div className="mb-2 mt-6 text-sm font-semibold text-gray-700">Skill Gap Analysis</div>
            <div className="overflow-visible rounded-2xl border">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Skill</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">On Bench</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Expiring (30d)</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Total Supply</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Open Demand</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-700">Gap</th>
                  </tr>
                </thead>
                <tbody className="divide-y bg-white">
                  {gapRows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500">
                        No bench, expiring, or open-demand skills to compare yet.
                      </td>
                    </tr>
                  ) : (
                    gapRows.map((r) => (
                      <tr key={r.skill} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold text-gray-900">{r.skill}</td>
                        <td className="px-4 py-3 text-gray-700">{r.current_bench_count}</td>
                        <td className="px-4 py-3 text-gray-700">{r.expiring_allocations_count_30d}</td>
                        <td className="px-4 py-3 text-gray-700">{r.total_projected_supply}</td>
                        <td className="px-4 py-3 text-gray-700">{r.open_demand_count}</td>
                        <td className={cx("px-4 py-3 font-semibold", r.gap < 0 ? "text-rose-700" : "text-emerald-700")}>
                          {r.gap > 0 ? `+${r.gap}` : r.gap}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
