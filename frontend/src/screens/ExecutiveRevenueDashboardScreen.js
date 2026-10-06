// S-241/HRMS-0212 Executive Revenue Dashboard + S-267 BU/Partner
// targets + S-244 Pipeline Coverage. Every figure here is a direct
// read of the shared backend calculations (calculate_weighted_forecast
// etc.) -- no local recalculation, per BR-0212-01.
//
// 2026-08-06: wired 2 previously-orphaned wrappers (working backend +
// api/ function, never imported by any screen):
//  - getBuTarget (GET /revenue-targets/bu/:id) -- auto-loads the
//    currently-set target/actual/status for the selected BU + fiscal
//    year the moment both are picked, instead of only showing a result
//    after re-submitting a new target via createBuTarget.
//  - getPipelineCoverage (GET /revenue-targets/pipeline-coverage) --
//    new "Pipeline Coverage" widget: how many multiples of a revenue
//    target the open (non-WON/LOST) pipeline currently covers.
import { useEffect, useState } from "react";
import { LineChart, Plus, Target } from "lucide-react";
import { Card, Button, Input } from "../components/ui";
import { getExecutiveDashboard, getPipelineCoverage } from "../services/api/revenueTargets";
import { listBusinessUnits } from "../services/api/rbac";
import GoalTree from "../components/GoalTree";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

// S-244 Pipeline Coverage -- how many multiples of a chosen revenue
// target the currently-open (non-WON/LOST) pipeline covers, scoped to
// whatever BU/client visibility the logged-in user already has
// (revenue.view -- same scope as the dashboard totals above).
function PipelineCoverageWidget() {
  const [targetAmount, setTargetAmount] = useState("");
  const [coverage, setCoverage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleCheck = async () => {
    setError("");
    const usdCents = Math.round(parseFloat(targetAmount || "0") * 100);
    if (!usdCents || usdCents <= 0) {
      setError("Enter a positive revenue target.");
      return;
    }
    setLoading(true);
    try {
      const data = await getPipelineCoverage(usdCents);
      setCoverage(data);
    } catch (err) {
      setError(err.message || "Failed to compute pipeline coverage.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-gray-900">
        <Target className="h-4 w-4" /> Pipeline Coverage
      </div>
      <p className="mb-3 text-xs text-gray-500">
        Open pipeline (excludes WON/LOST) as a multiple of a revenue target -- e.g. 3x coverage
        against a quota is the common healthy-pipeline benchmark.
      </p>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Input
          label="Revenue Target (USD)"
          value={targetAmount}
          onChange={setTargetAmount}
          placeholder="2000000"
        />
        <div className="flex items-end">
          <Button onClick={handleCheck} disabled={loading}>
            {loading ? "Checking…" : "Check Coverage"}
          </Button>
        </div>
      </div>
      {coverage ? (
        <div className="mt-3 rounded-lg border bg-white p-2 text-xs text-gray-700">
          Target: <span className="font-semibold">{formatUsdCents(coverage.revenue_target_usd_cents)}</span>
          {" · "}
          Coverage Ratio:{" "}
          <span className="font-semibold">
            {coverage.coverage_ratio == null ? "—" : `${coverage.coverage_ratio.toFixed(2)}x`}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export default function ExecutiveRevenueDashboardScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [businessUnitNames, setBusinessUnitNames] = useState({});

  const load = async () => {
    setLoading(true);
    try {
      const data = await getExecutiveDashboard();
      setDashboard(data);
    } catch (err) {
      console.error("Failed to load executive revenue dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    listBusinessUnits()
      .then((list) => {
        const names = {};
        (list || []).forEach((bu) => { names[bu.id] = bu.name; });
        setBusinessUnitNames(names);
      })
      .catch((err) => console.error("Failed to load business units:", err));
  }, []);

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Executive Revenue"
        subtitle="Pipeline, won, lost, and weighted forecast -- every figure calls the same shared calculation as the Opportunity Pipeline."
        icon={<LineChart className="h-4 w-4" />}
      >
        {loading || !dashboard ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Total Pipeline</div>
                <div className="text-lg font-semibold text-gray-900">{formatUsdCents(dashboard.total_pipeline_usd_cents)}</div>
              </div>
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Won</div>
                <div className="text-lg font-semibold text-emerald-700">{formatUsdCents(dashboard.won_usd_cents)}</div>
              </div>
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Lost</div>
                <div className="text-lg font-semibold text-rose-700">{formatUsdCents(dashboard.lost_usd_cents)}</div>
              </div>
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Weighted Forecast</div>
                <div className="text-lg font-semibold text-gray-900">{formatUsdCents(dashboard.weighted_forecast_usd_cents)}</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase text-gray-500">By Business Unit</div>
              <div className="space-y-2">
                {dashboard.by_business_unit.map((bu) => (
                  <div key={bu.business_unit_id ?? "unassigned"} className="flex items-center justify-between rounded-xl border bg-white p-3 text-sm">
                    <span className="font-medium text-gray-700">
                      {bu.business_unit_id ? (businessUnitNames[bu.business_unit_id] || `BU #${bu.business_unit_id}`) : "Unassigned"}
                    </span>
                    <span className="text-gray-600">Pipeline: {formatUsdCents(bu.pipeline_usd_cents)}</span>
                    <span className="text-emerald-700">Won: {formatUsdCents(bu.won_usd_cents)}</span>
                    <span className="text-gray-600">Weighted: {formatUsdCents(bu.weighted_forecast_usd_cents)}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <PipelineCoverageWidget />

        <GoalTree />

        <Button variant="ghost" className="mt-4" onClick={load}>
          <Plus className="h-4 w-4" /> Refresh
        </Button>
      </Card>
    </div>
  );
}
