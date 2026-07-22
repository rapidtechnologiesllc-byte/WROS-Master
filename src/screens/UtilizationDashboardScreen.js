// S-254 (Employee Utilization Dashboard) + S-255 (Bench Cost Visibility).
import { useEffect, useState } from "react";
import { BarChart3, RefreshCw, AlertTriangle, DollarSign } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getUtilizationSummary, getBenchCostSummary } from "../services/api/utilization";

const usd = (cents) => (cents == null ? "—" : `$${(cents / 100).toFixed(2)}`);

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
        subtitle="Latest weekly billable-vs-bench utilization per employee. Below-50% flagged as a low-utilization alert."
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

        {utilization ? (
          <div className="mb-4 flex flex-wrap gap-4 text-sm text-gray-700">
            <div>
              Average utilization:{" "}
              <span className="font-semibold">
                {utilization.average_utilization_pct != null ? `${utilization.average_utilization_pct}%` : "—"}
              </span>
            </div>
            <div>
              Low-utilization alerts:{" "}
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
                <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">No utilization data recorded yet.</td></tr>
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
        subtitle="Daily/monthly cost and running total for every employee currently on the bench."
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
