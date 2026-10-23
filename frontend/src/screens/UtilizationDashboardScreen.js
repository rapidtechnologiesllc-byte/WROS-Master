import { Link } from "react-router-dom";
// S-254 (Employee Utilization Dashboard) + S-255 (Bench Cost Visibility).
import { useEffect, useState } from "react";
import { BarChart3, RefreshCw, AlertTriangle, DollarSign, Calculator } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getUtilizationSummary, getBenchCostSummary, recomputeUtilization } from "../services/api/utilization";

const usd = (cents) => (cents == null ? "—" : `$${(cents / 100).toFixed(2)}`);

// Utilization is recorded every week by the utilization_snapshot job for every billable
// employee. "Recompute now" reruns it for the recent weeks (e.g. after late timesheet approvals);
// the backend allows it only to roles that may create employee records.
function RecomputeUtilizationButton({ onRecomputed }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleRecompute = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await recomputeUtilization();
      setMessage(`Recomputed ${res.snapshots} weekly figures for ${res.employees} employees.`);
      onRecomputed();
    } catch (err) {
      setError(err.message || "Failed to recompute utilization.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" disabled={busy} onClick={handleRecompute}>
        <Calculator className="h-4 w-4" /> {busy ? "Recomputing…" : "Recompute now"}
      </Button>
      {message ? <span className="text-xs text-gray-600">{message}</span> : null}
      {error ? <span className="text-xs text-rose-700">{error}</span> : null}
    </div>
  );
}

export default function UtilizationDashboardScreen() {
  const [utilization, setUtilization] = useState(null);
  const [benchCost, setBenchCost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [utilRes, costRes] = await Promise.all([getUtilizationSummary(), getBenchCostSummary()]);
      setUtilization(utilRes);
      setBenchCost(costRes);
    } catch (err) {
      setError(err.message || "Failed to load utilization/cost data.");
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
        title="Employee Utilization Dashboard"
        subtitle={
          utilization?.utilization_target_pct != null
            ? `Latest weekly billable utilization per billable employee, recorded every week. Below the ${utilization.utilization_target_pct}% target is flagged.`
            : "Latest weekly billable utilization per billable employee, recorded every week."
        }
        icon={<BarChart3 className="h-4 w-4" />}
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

        <div className="mb-4">
          <RecomputeUtilizationButton onRecomputed={load} />
        </div>

        {utilization ? (
          <div className="mb-4 flex flex-wrap gap-4 text-sm text-gray-700">
            <div>
              Average utilization:{" "}
              <span className="font-semibold">
                {utilization.average_utilization_pct != null ? `${utilization.average_utilization_pct}%` : "—"}
              </span>
            </div>
            <div>
              Target: <span className="font-semibold">{utilization.utilization_target_pct}%</span>
            </div>
            <div>
              Below target:{" "}
              <span className="font-semibold text-amber-700">{utilization.low_utilization_count}</span>
            </div>
          </div>
        ) : null}

        <div className="overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Latest Utilization</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Week Of</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">Loading…</td></tr>
              ) : !utilization || utilization.employees.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">No utilization recorded yet: the weekly job fills this in, or use Recompute now.</td></tr>
              ) : (
                utilization.employees.map((e) => (
                  <tr key={e.employee_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">{e.employee_name}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {e.latest_utilization_pct != null ? `${e.latest_utilization_pct}%` : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{e.latest_period_start || "—"}</td>
                    <td className="px-4 py-3">
                      {e.is_low_utilization ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                          <AlertTriangle className="h-3 w-3" /> Low
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="Bench Cost Visibility"
        subtitle="Daily/monthly loaded cost and running total for every employee on the bench (same figures as the P&L)."
        right={<Link to="/workforce/bench" className="text-xs font-semibold text-blue-700 hover:underline">Bench detail</Link>}
        icon={<DollarSign className="h-4 w-4" />}
      >
        {benchCost ? (
          <div className="mb-4 text-sm text-gray-700">
            Total running bench cost:{" "}
            <span className="font-semibold">{usd(benchCost.total_running_cost_usd_cents)}</span>
          </div>
        ) : null}
        <div className="overflow-visible rounded-2xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Employee</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Days on Bench</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Daily</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Monthly</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-700">Running Total</th>
              </tr>
            </thead>
            <tbody className="divide-y bg-white">
              {loading ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">Loading…</td></tr>
              ) : !benchCost || benchCost.employees.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">No one is currently on the bench.</td></tr>
              ) : (
                benchCost.employees.map((e) => (
                  <tr key={e.employee_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">{e.employee_name}</td>
                    <td className="px-4 py-3 text-gray-700">{e.days_on_bench}</td>
                    <td className="px-4 py-3 text-gray-700">{usd(e.daily_cost_usd_cents)}</td>
                    <td className="px-4 py-3 text-gray-700">{usd(e.monthly_cost_usd_cents)}</td>
                    <td className="px-4 py-3 font-semibold text-gray-900">{usd(e.running_total_usd_cents)}</td>
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
