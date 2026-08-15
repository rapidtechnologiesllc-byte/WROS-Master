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
import { Card, Button, Input, Select } from "../components/ui";
import {
  getExecutiveDashboard,
  createBuTarget,
  getBuTarget,
  createPartnerGoal,
  getPartnerPosition,
  getRevenueToDemandProjection,
  getPipelineCoverage,
} from "../services/api/revenueTargets";
import { listBusinessUnits } from "../services/api/rbac";
import { searchUsers } from "../services/api/users";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

// A stored target is always ANNUAL now (the one number that matters);
// this is a pure even-division display breakdown, not a second set of
// stored rows -- "less clicks, more outcome": the system computes the
// breakdown, nobody re-enters the same number 17 times.
function PeriodBreakdown({ annualUsdCents }) {
  if (annualUsdCents == null) return null;
  const quarterly = annualUsdCents / 4;
  const halfYearly = annualUsdCents / 2;
  const monthly = annualUsdCents / 12;
  return (
    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-gray-700">
      <div className="rounded-lg border bg-white p-2">
        <div className="text-gray-500">Monthly</div>
        <div className="font-semibold">{formatUsdCents(monthly)}</div>
      </div>
      <div className="rounded-lg border bg-white p-2">
        <div className="text-gray-500">Quarterly</div>
        <div className="font-semibold">{formatUsdCents(quarterly)}</div>
      </div>
      <div className="rounded-lg border bg-white p-2">
        <div className="text-gray-500">Half-Yearly</div>
        <div className="font-semibold">{formatUsdCents(halfYearly)}</div>
      </div>
    </div>
  );
}

function BuTargetForm() {
  const [businessUnits, setBusinessUnits] = useState([]);
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [fiscalYear, setFiscalYear] = useState("2026");
  const [amount, setAmount] = useState("");
  const [result, setResult] = useState(null);
  const [workforceProjection, setWorkforceProjection] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listBusinessUnits()
      .then((list) => setBusinessUnits(list || []))
      .catch((err) => console.error("Failed to load business units:", err));
  }, []);

  // Picking a BU also shows its current-month Revenue-to-Workforce
  // projection -- no extra click, the agent surfaces what it already
  // knows the moment there's a BU to know it about.
  useEffect(() => {
    if (!businessUnitId) {
      setWorkforceProjection(null);
      return;
    }
    const now = new Date();
    getRevenueToDemandProjection(businessUnitId, now.getFullYear(), now.getMonth() + 1)
      .then(setWorkforceProjection)
      .catch((err) => {
        console.error("Failed to load workforce projection:", err);
        setWorkforceProjection(null);
      });
  }, [businessUnitId]);

  // Picking a BU + fiscal year also loads whatever ANNUAL target is
  // already on record for it (GET /revenue-targets/bu/:id) -- previously
  // the only way to see a target/actual/status was to re-submit one via
  // createBuTarget. get_bu_target_vs_actual never errors on "no target
  // set yet" (returns status "NO_TARGET"), so this is safe to auto-fire.
  useEffect(() => {
    if (!businessUnitId || !fiscalYear) {
      setResult(null);
      return;
    }
    let cancelled = false;
    getBuTarget(Number(businessUnitId), "ANNUAL", Number(fiscalYear))
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((err) => {
        console.error("Failed to load existing BU target:", err);
        if (!cancelled) setResult(null);
      });
    return () => {
      cancelled = true;
    };
  }, [businessUnitId, fiscalYear]);

  const buOptions = [
    { label: "Select Business Unit", value: "", disabled: true },
    ...(businessUnits || []).map((bu) => ({ label: bu.name, value: String(bu.id) })),
  ];

  const handleSave = async () => {
    setError("");
    if (!businessUnitId) {
      setError("Please select a Business Unit");
      return;
    }
    if (!amount) {
      setError("Please enter an Annual Target");
      return;
    }
    try {
      const res = await createBuTarget({
        business_unit_id: Number(businessUnitId),
        target_period: "ANNUAL",
        fiscal_year: Number(fiscalYear) || new Date().getFullYear(),
        target_amount_usd_cents: Math.round(parseFloat(amount) * 100),
      });
      setResult(res);
    } catch (err) {
      setError(err.message || "Failed to set target.");
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Set BU Annual Revenue Target</div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Select label="Business Unit" value={businessUnitId} onChange={setBusinessUnitId} options={buOptions} />
        <Input label="Fiscal Year" value={fiscalYear} onChange={setFiscalYear} />
        <Input label="Annual Target (USD)" value={amount} onChange={setAmount} placeholder="2000000" />
      </div>
      <Button className="mt-3" onClick={handleSave}>Set Target</Button>
      {workforceProjection ? (
        <div className="mt-3 rounded-lg border bg-white p-2 text-xs text-gray-700">
          <div className="mb-1 font-semibold text-gray-900">This Month's Workforce Need (Revenue-to-Demand)</div>
          <div>Current headcount: <span className="font-semibold">{workforceProjection.current_headcount}</span></div>
          <div>
            Revenue per head:{" "}
            <span className="font-semibold">{formatUsdCents(workforceProjection.revenue_per_head_usd_cents)}</span>
          </div>
          <div>
            Projected need:{" "}
            <span className="font-semibold">{workforceProjection.projected_headcount_needed ?? "—"}</span>
            {" "}(already open in pipeline: {workforceProjection.open_demand_headcount})
          </div>
          {workforceProjection.workforce_gap != null ? (
            <div className={workforceProjection.workforce_gap > 0 ? "text-rose-700" : "text-emerald-700"}>
              Gap to plan for: <span className="font-semibold">{workforceProjection.workforce_gap}</span>
            </div>
          ) : null}
        </div>
      ) : null}
      {result ? (
        <>
          <div className="mt-3 text-xs text-gray-700">
            {result.status === "NO_TARGET" ? "No target set yet for this BU/year" : "Current Target"} ·{" "}
            Target: {formatUsdCents(result.target_amount_usd_cents)} · Actual: {formatUsdCents(result.actual_usd_cents)} ·{" "}
            <span className="font-semibold">{result.status}</span>
          </div>
          <PeriodBreakdown annualUsdCents={result.target_amount_usd_cents} />
        </>
      ) : null}
    </div>
  );
}

function PartnerGoalForm() {
  const [partners, setPartners] = useState([]);
  const [partnerUserId, setPartnerUserId] = useState("");
  const [fiscalYear, setFiscalYear] = useState("2026");
  const [amount, setAmount] = useState("");
  const [position, setPosition] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    searchUsers({ permission_role: "Partner", limit: 100 })
      .then((data) => setPartners(data?.users || []))
      .catch((err) => console.error("Failed to load Partners:", err));
  }, []);

  const partnerOptions = [
    { label: "Select Partner", value: "", disabled: true },
    ...(partners || []).map((p) => ({ label: `${p.user_name} (${p.user_email})`, value: p.user_id })),
  ];

  const handleSave = async () => {
    setError("");
    if (!partnerUserId) {
      setError("Please select a Partner");
      return;
    }
    if (!amount) {
      setError("Please enter an Annual Target");
      return;
    }
    try {
      await createPartnerGoal({
        partner_user_id: partnerUserId,
        target_period: "ANNUAL",
        fiscal_year: Number(fiscalYear) || new Date().getFullYear(),
        target_amount_usd_cents: Math.round(parseFloat(amount) * 100),
      });
      const pos = await getPartnerPosition(partnerUserId);
      setPosition(pos);
    } catch (err) {
      setError(err.message || "Failed to set goal (CEO/Super User only).");
    }
  };

  const currentYearTarget = position?.years?.find((y) => String(y.fiscal_year) === fiscalYear);

  return (
    <div className="mt-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Set Partner Annual Goal (CEO only)</div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Select label="Partner" value={partnerUserId} onChange={setPartnerUserId} options={partnerOptions} />
        <Input label="Fiscal Year" value={fiscalYear} onChange={setFiscalYear} />
        <Input label="Annual Target (USD)" value={amount} onChange={setAmount} placeholder="2000000" />
      </div>
      <Button className="mt-3" onClick={handleSave}>Set Goal</Button>
      {position ? (
        <>
          <div className="mt-3 space-y-1 text-xs text-gray-700">
            <div>
              Cumulative deficit: <span className="font-semibold text-rose-700">{formatUsdCents(position.cumulative_deficit_usd_cents)}</span>
            </div>
            <div>
              This FY surplus: <span className="font-semibold text-emerald-700">{formatUsdCents(position.current_fy_surplus_usd_cents)}</span>
            </div>
          </div>
          <PeriodBreakdown annualUsdCents={currentYearTarget?.target_amount_usd_cents} />
        </>
      ) : null}
    </div>
  );
}

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

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BuTargetForm />
          <PartnerGoalForm />
        </div>

        <Button variant="ghost" className="mt-4" onClick={load}>
          <Plus className="h-4 w-4" /> Refresh
        </Button>
      </Card>
    </div>
  );
}
