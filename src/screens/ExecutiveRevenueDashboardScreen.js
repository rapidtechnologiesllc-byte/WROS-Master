// S-241/HRMS-0212 Executive Revenue Dashboard + S-267 BU/Partner
// targets + S-244 Pipeline Coverage. Every figure here is a direct
// read of the shared backend calculations (calculate_weighted_forecast
// etc.) -- no local recalculation, per BR-0212-01.
import { useEffect, useState } from "react";
import { LineChart, Plus } from "lucide-react";
import { Card, Button, Input, Select } from "../components/ui";
import {
  getExecutiveDashboard,
  createBuTarget,
  createPartnerGoal,
  getPartnerPosition,
} from "../services/api/revenueTargets";

const PERIODS = ["ANNUAL", "H1", "H2", "Q1", "Q2", "Q3", "Q4"];

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function BuTargetForm() {
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [targetPeriod, setTargetPeriod] = useState("ANNUAL");
  const [fiscalYear, setFiscalYear] = useState("2026");
  const [amount, setAmount] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setError("");
    try {
      const res = await createBuTarget({
        business_unit_id: Number(businessUnitId),
        target_period: targetPeriod,
        fiscal_year: Number(fiscalYear),
        target_amount_usd_cents: Math.round(parseFloat(amount || "0") * 100),
      });
      setResult(res);
    } catch (err) {
      setError(err.message || "Failed to set target.");
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Set BU Revenue Target</div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Input label="Business Unit ID" value={businessUnitId} onChange={setBusinessUnitId} placeholder="1" />
        <Select label="Period" value={targetPeriod} onChange={setTargetPeriod} options={PERIODS} />
        <Input label="Fiscal Year" value={fiscalYear} onChange={setFiscalYear} />
        <Input label="Target (USD)" value={amount} onChange={setAmount} placeholder="2000000" />
      </div>
      <Button className="mt-3" onClick={handleSave}>Set Target</Button>
      {result ? (
        <div className="mt-3 text-xs text-gray-700">
          Target: {formatUsdCents(result.target_amount_usd_cents)} · Actual: {formatUsdCents(result.actual_usd_cents)} ·{" "}
          <span className="font-semibold">{result.status}</span>
        </div>
      ) : null}
    </div>
  );
}

function PartnerGoalForm() {
  const [partnerUserId, setPartnerUserId] = useState("");
  const [fiscalYear, setFiscalYear] = useState("2026");
  const [amount, setAmount] = useState("");
  const [position, setPosition] = useState(null);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setError("");
    try {
      await createPartnerGoal({
        partner_user_id: partnerUserId, target_period: "ANNUAL",
        fiscal_year: Number(fiscalYear), target_amount_usd_cents: Math.round(parseFloat(amount || "0") * 100),
      });
      const pos = await getPartnerPosition(partnerUserId);
      setPosition(pos);
    } catch (err) {
      setError(err.message || "Failed to set goal (CEO/Super User only).");
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Set Partner Goal (CEO only)</div>
      {error ? <div className="mb-2 text-xs text-rose-700">{error}</div> : null}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Input label="Partner User ID" value={partnerUserId} onChange={setPartnerUserId} placeholder="troy" />
        <Input label="Fiscal Year" value={fiscalYear} onChange={setFiscalYear} />
        <Input label="Annual Target (USD)" value={amount} onChange={setAmount} placeholder="2000000" />
      </div>
      <Button className="mt-3" onClick={handleSave}>Set Goal</Button>
      {position ? (
        <div className="mt-3 space-y-1 text-xs text-gray-700">
          <div>
            Cumulative deficit: <span className="font-semibold text-rose-700">{formatUsdCents(position.cumulative_deficit_usd_cents)}</span>
          </div>
          <div>
            This FY surplus: <span className="font-semibold text-emerald-700">{formatUsdCents(position.current_fy_surplus_usd_cents)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ExecutiveRevenueDashboardScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

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
  }, []);

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Executive Revenue Dashboard"
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
                    <span className="font-medium text-gray-700">BU #{bu.business_unit_id ?? "Unassigned"}</span>
                    <span className="text-gray-600">Pipeline: {formatUsdCents(bu.pipeline_usd_cents)}</span>
                    <span className="text-emerald-700">Won: {formatUsdCents(bu.won_usd_cents)}</span>
                    <span className="text-gray-600">Weighted: {formatUsdCents(bu.weighted_forecast_usd_cents)}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

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
