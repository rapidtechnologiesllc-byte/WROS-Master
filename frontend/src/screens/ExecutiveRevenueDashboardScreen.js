// S-241/HRMS-0212 Executive Revenue Dashboard + S-267 BU/Partner
// targets + S-244 Pipeline Coverage. Every figure here is a direct
// read of the shared backend calculations (calculate_weighted_forecast
// etc.) -- no local recalculation, per BR-0212-01.
//
// Pipeline Coverage is read straight off the dashboard response: open
// pipeline against the stored FY revenue target (org target, or the
// viewer's BU targets), never a target typed in on this screen.
import { useEffect, useState } from "react";
import { LineChart, Plus } from "lucide-react";
import { Card, Button } from "../components/ui";
import { getExecutiveDashboard } from "../services/api/revenueTargets";
import { listBusinessUnits } from "../services/api/rbac";
import GoalTree from "../components/GoalTree";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

// Colour for the backend's coverage band (HEALTHY / THIN / LOW / NO_TARGET).
const COVERAGE_TONE = {
  HEALTHY: "text-emerald-700",
  THIN: "text-amber-700",
  LOW: "text-rose-700",
};

const formatCoverage = (ratio) => (ratio == null ? "—" : `${ratio.toFixed(2)}x`);

// S-244 Pipeline Coverage -- open (non-WON/LOST) pipeline as a multiple
// of the FY revenue target, in the same scope as the totals beside it.
function PipelineCoverageTile({ dashboard }) {
  const hasTarget = dashboard.pipeline_coverage_target_usd_cents != null;
  return (
    <div className="rounded-xl border bg-white p-3">
      <div className="text-xs text-gray-500">Pipeline Coverage</div>
      <div className={`text-lg font-semibold ${COVERAGE_TONE[dashboard.pipeline_coverage_status] || "text-gray-900"}`}>
        {formatCoverage(dashboard.pipeline_coverage)}
      </div>
      <div className="text-xs text-gray-500">
        {hasTarget
          ? `of ${formatUsdCents(dashboard.pipeline_coverage_target_usd_cents)} FY target · ${dashboard.pipeline_coverage_benchmark}x is healthy`
          : "No FY revenue target set (Goals)"}
      </div>
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
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
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
              <PipelineCoverageTile dashboard={dashboard} />
            </div>

            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase text-gray-500">By Business Unit</div>
              <div className="space-y-2">
                {dashboard.by_business_unit.map((bu) => {
                  const metrics = (dashboard.bu_metrics || []).find((m) => m.business_unit_id === bu.business_unit_id);
                  return (
                    <div key={bu.business_unit_id ?? "unassigned"} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-white p-3 text-sm">
                      <span className="font-medium text-gray-700">
                        {bu.business_unit_id ? (businessUnitNames[bu.business_unit_id] || `BU #${bu.business_unit_id}`) : "Unassigned"}
                      </span>
                      <span className="text-gray-600">Pipeline: {formatUsdCents(bu.pipeline_usd_cents)}</span>
                      <span className="text-emerald-700">Won: {formatUsdCents(bu.won_usd_cents)}</span>
                      <span className="text-gray-600">Weighted: {formatUsdCents(bu.weighted_forecast_usd_cents)}</span>
                      <span className={COVERAGE_TONE[metrics?.pipeline_coverage_status] || "text-gray-500"}>
                        Coverage: {metrics?.target_usd_cents ? formatCoverage(metrics.pipeline_coverage) : "no target"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        <GoalTree />

        <Button variant="ghost" className="mt-4" onClick={load}>
          <Plus className="h-4 w-4" /> Refresh
        </Button>
      </Card>
    </div>
  );
}
