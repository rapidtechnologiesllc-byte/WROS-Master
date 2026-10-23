// Partner Home (CEO 2026-10-17): the one partner screen. Every business unit the partner leads --
// all of them in total, or one through the BU filter: performance KPIs, trend and actions, FY
// targets vs actuals per company, and operations (demand, pre-onboarding, certifications, buddy
// program, core certified). Scope is enforced server-side; org-level users pick a partner.
import { Fragment, useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, Award, Briefcase, Target, TrendingUp, Users, X } from "lucide-react";
import { Card } from "../components/ui";
import FinancialOutlookPanel from "../components/FinancialOutlookPanel";
import { getPartnerDashboard, getPartnerPerformance } from "../services/api/partnerHome";

const TARGET_METRICS = [
  { key: "revenue", label: "Revenue", usd: true },
  { key: "headcount", label: "Billable headcount" },
  { key: "new_logos", label: "New logos" },
];

const usd = (value) => {
  const n = Number(value || 0);
  return Math.abs(n) >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

const fmt = (value, isUsd) => {
  if (value === null || value === undefined) return "--";
  return isUsd ? usd(value) : Number(value).toLocaleString();
};

const pct = (value) => `${Number(value || 0).toFixed(1)}%`;

function TargetCell({ cell, isUsd }) {
  if (!cell) return <span className="text-gray-400">--</span>;
  const progress = cell.progress_pct;
  return (
    <div>
      <div className="font-semibold text-gray-900">
        {fmt(cell.actual, isUsd)}{" "}
        <span className="text-xs font-normal text-gray-500">/ {cell.target ? fmt(cell.target, isUsd) : "no target"}</span>
      </div>
      {progress !== null && progress !== undefined && (
        <div className="mt-1 h-1.5 w-full rounded bg-gray-100">
          <div
            className={`h-1.5 rounded ${progress >= 100 ? "bg-green-500" : progress >= 60 ? "bg-blue-500" : "bg-amber-500"}`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, icon: Icon, tone = "text-blue-500" }) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-semibold uppercase text-gray-500">{label}</div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
        </div>
        <Icon className={`h-6 w-6 ${tone}`} />
      </div>
    </Card>
  );
}

export default function PartnerHomeScreen() {
  const [partnerId, setPartnerId] = useState("");
  const [buId, setBuId] = useState("");
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [dashboard, setDashboard] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [partnerChoices, setPartnerChoices] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setActionError(null);
      try {
        const scope = { partnerUserId: partnerId, businessUnitId: buId };
        const [board, perf] = await Promise.all([
          getPartnerDashboard(scope),
          getPartnerPerformance({ ...scope, yearMonth: month }),
        ]);
        if (cancelled) return;
        if (board?.status === "needs_partner") {
          setPartnerChoices(board.partners || []);
          setDashboard(null);
          setPerformance(null);
          return;
        }
        if (board?.partners) setPartnerChoices(board.partners);
        setDashboard(board);
        setPerformance(perf?.data || null);
      } catch (err) {
        if (!cancelled) setActionError(`Failed to load the partner home: ${err.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [partnerId, buId, month]);

  const picker = partnerChoices ? (
    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-gray-700" htmlFor="partner-picker">Partner</label>
      <select
        id="partner-picker"
        value={partnerId || dashboard?.partner?.user_id || ""}
        onChange={(e) => { setPartnerId(e.target.value); setBuId(""); }}
        className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
      >
        <option value="">Select a partner</option>
        {partnerChoices.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      {partnerChoices.length === 0 && (
        <span className="text-sm text-amber-700">
          No partners yet: set the Partner on a business unit in Users &amp; Access → Business Units.
        </span>
      )}
    </div>
  ) : null;

  const errorBanner = actionError && (
    <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-4">
      <div className="flex items-center gap-3 text-red-800">
        <AlertTriangle className="h-5 w-5 text-red-600" />
        <span>{actionError}</span>
      </div>
      <button onClick={() => setActionError(null)} className="text-red-600 hover:text-red-800" aria-label="Dismiss">
        <X className="h-4 w-4" />
      </button>
    </div>
  );

  if (loading && !dashboard) return <div className="p-6 text-center text-gray-500">Loading partner home...</div>;
  if (!dashboard) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 p-6">
        <h1 className="text-3xl font-bold text-gray-900">Partner Home</h1>
        {errorBanner}
        {picker || (!actionError && <div className="text-center text-gray-500">No data available</div>)}
      </div>
    );
  }

  const units = dashboard.business_units || [];
  const kpis = performance?.kpis;
  const ops = dashboard.data || {};
  const buName = (id) => units.find((bu) => bu.id === id)?.name || `BU ${id}`;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {errorBanner}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Partner Home</h1>
          <div className="text-sm text-gray-600">
            {dashboard.partner?.name} · {units.length} business unit(s) · {dashboard.fy_label}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {picker}
          {units.length > 1 && (
            <select
              aria-label="Business unit"
              value={buId}
              onChange={(e) => setBuId(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">All my business units</option>
              {units.map((bu) => <option key={bu.id} value={bu.id}>{bu.name}</option>)}
            </select>
          )}
          <input
            type="month"
            aria-label="Month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {units.length === 0 ? (
        <Card>
          <div className="text-sm text-gray-600">
            {dashboard.partner?.name} is not the partner of any business unit yet. Set the Partner on each business unit
            in Users &amp; Access → Business Units.
          </div>
        </Card>
      ) : (
        <>
          {kpis && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
              <Stat label="Revenue" value={usd(kpis.revenue_usd)} icon={TrendingUp} />
              <Stat label="Gross margin" value={pct(kpis.gross_margin_pct)} icon={TrendingUp} tone="text-green-500" />
              <Stat label="Utilization" value={pct(kpis.practice_utilization_pct)} icon={Users} tone="text-indigo-500" />
              <Stat label="New logos" value={kpis.net_new_logos} icon={Target} tone="text-green-500" />
              <Stat label="Growth YoY" value={pct(kpis.practice_growth_yoy_pct)} icon={TrendingUp} tone="text-purple-500" />
            </div>
          )}

          {kpis && !buId && kpis.by_business_unit.length > 1 && (
            <Card title={`By business unit · ${kpis.period}`}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase text-gray-500">
                      <th className="px-3 py-2">Business unit</th>
                      <th className="px-3 py-2">Revenue</th>
                      <th className="px-3 py-2">Margin</th>
                      <th className="px-3 py-2">Utilization</th>
                      <th className="px-3 py-2">New logos</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b bg-gray-50 font-semibold">
                      <td className="px-3 py-2">All my business units</td>
                      <td className="px-3 py-2">{usd(kpis.revenue_usd)}</td>
                      <td className="px-3 py-2">{pct(kpis.gross_margin_pct)}</td>
                      <td className="px-3 py-2">{pct(kpis.practice_utilization_pct)}</td>
                      <td className="px-3 py-2">{kpis.net_new_logos}</td>
                    </tr>
                    {kpis.by_business_unit.map((row) => (
                      <tr key={row.business_unit_id} className="border-b">
                        <td className="px-3 py-2">
                          <button className="text-left text-bx-navy hover:underline" onClick={() => setBuId(String(row.business_unit_id))}>
                            {row.business_unit_name || buName(row.business_unit_id)}
                          </button>
                        </td>
                        <td className="px-3 py-2">{usd(row.revenue_usd)}</td>
                        <td className="px-3 py-2">{pct(row.gross_margin_pct)}</td>
                        <td className="px-3 py-2">{pct(row.practice_utilization_pct)}</td>
                        <td className="px-3 py-2">{row.net_new_logos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {performance?.actions?.length > 0 && (
            <Card title="Recommended actions">
              <div className="space-y-3">
                {performance.actions.map((action) => (
                  <div
                    key={action.category}
                    className={`flex gap-3 rounded-lg p-3 ${action.priority === "HIGH" ? "border border-red-200 bg-red-50" : "border border-amber-200 bg-amber-50"}`}
                  >
                    <AlertCircle className={`mt-0.5 h-5 w-5 flex-shrink-0 ${action.priority === "HIGH" ? "text-red-600" : "text-amber-600"}`} />
                    <div>
                      <div className="font-semibold text-gray-900">{action.message}</div>
                      <div className="mt-1 text-xs text-gray-600">{action.category}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {performance?.trend?.length > 0 && (
            <Card title={`${performance.trend.length}-month trend`}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase text-gray-500">
                      <th className="px-3 py-2">Month</th>
                      <th className="px-3 py-2">Revenue</th>
                      <th className="px-3 py-2">Margin</th>
                      <th className="px-3 py-2">Utilization</th>
                      <th className="px-3 py-2">New logos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {performance.trend.map((row) => (
                      <tr key={row.period} className="border-b last:border-0">
                        <td className="px-3 py-2 font-semibold">{row.period}</td>
                        <td className="px-3 py-2">{usd(row.revenue_usd)}</td>
                        <td className="px-3 py-2">{pct(row.gross_margin_pct)}</td>
                        <td className="px-3 py-2">{pct(row.practice_utilization_pct)}</td>
                        <td className="px-3 py-2">{row.net_new_logos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <FinancialOutlookPanel title="My business units: plan vs actual" businessUnitId={buId || undefined} />

          <Card title="FY targets vs actuals">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase text-gray-500">
                    <th className="px-3 py-2">Company / Business unit</th>
                    {TARGET_METRICS.map((m) => <th key={m.key} className="px-3 py-2">{m.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b bg-gray-50">
                    <td className="px-3 py-2 font-bold">All companies</td>
                    {TARGET_METRICS.map((m) => (
                      <td key={m.key} className="px-3 py-2"><TargetCell cell={dashboard.totals?.[m.key]} isUsd={m.usd} /></td>
                    ))}
                  </tr>
                  {(dashboard.by_company || []).map((company) => (
                    <Fragment key={company.company_id}>
                      <tr className="border-b">
                        <td className="px-3 py-2 font-semibold">{company.company}</td>
                        {TARGET_METRICS.map((m) => (
                          <td key={m.key} className="px-3 py-2"><TargetCell cell={company.metrics[m.key]} isUsd={m.usd} /></td>
                        ))}
                      </tr>
                      {company.business_units.map((bu) => (
                        <tr key={`${company.company_id}:${bu.bu_id}`} className="border-b">
                          <td className="px-3 py-2 pl-8 text-gray-700">
                            {bu.name}
                            {bu.head && <span className="ml-2 text-xs text-gray-500">Head: {bu.head}</span>}
                          </td>
                          {TARGET_METRICS.map((m) => (
                            <td key={m.key} className="px-3 py-2"><TargetCell cell={bu.metrics[m.key]} isUsd={m.usd} /></td>
                          ))}
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-gray-500">Targets are set on Leadership → Goals &amp; Revenue.</p>
          </Card>

          {dashboard.data && (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
                <Stat label="Open positions" value={ops.current_demand?.open_positions || 0} icon={Briefcase} />
                <Stat label="Pre-onboarding" value={ops.pre_onboarding_pipeline?.in_pre_onboarding || 0} icon={TrendingUp} tone="text-purple-500" />
                <Stat label="Certified" value={ops.certifications?.total_active || 0} icon={Award} tone="text-green-500" />
                <Stat label="Buddy program" value={ops.buddy_program?.total_in_program || 0} icon={Users} tone="text-indigo-500" />
                <Stat label="Core certified" value={ops.core_certified_employees?.length || 0} icon={Award} tone="text-yellow-500" />
              </div>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card title="Certification status">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span>Total certified</span><span className="font-bold">{ops.certifications?.total_active || 0}</span></div>
                    <div className="flex justify-between text-orange-600"><span>Expiring within 30 days</span><span className="font-bold">{ops.certifications?.expiring_within_30_days || 0}</span></div>
                    <div className="flex justify-between text-red-600"><span>Expired</span><span className="font-bold">{ops.certifications?.already_expired || 0}</span></div>
                    {ops.certifications?.by_level && (
                      <div className="mt-3 space-y-1 border-t pt-3">
                        {Object.entries(ops.certifications.by_level).map(([level, count]) => (
                          <div key={level} className="flex justify-between"><span>{level}</span><span className="font-semibold">{count}</span></div>
                        ))}
                      </div>
                    )}
                  </div>
                </Card>
                <Card title="Buddy program">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span>In program</span><span className="font-bold">{ops.buddy_program?.total_in_program || 0}</span></div>
                    <div className="flex justify-between text-green-600"><span>On track</span><span className="font-bold">{ops.buddy_program?.on_track || 0}</span></div>
                    <div className="flex justify-between text-orange-600"><span>At risk</span><span className="font-bold">{ops.buddy_program?.at_risk || 0}</span></div>
                    <div className="flex justify-between text-green-600"><span>Completed this month</span><span className="font-bold">{ops.buddy_program?.completed_this_month || 0}</span></div>
                  </div>
                </Card>
              </div>

              <Card title="Core certified employees">
                {ops.core_certified_employees?.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left">
                          <th className="px-3 py-2 font-semibold">Employee</th>
                          <th className="px-3 py-2 font-semibold">Certification</th>
                          <th className="px-3 py-2 font-semibold">Earned</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ops.core_certified_employees.map((emp) => (
                          <tr key={`${emp.name}:${emp.certification}:${emp.earned_date}`} className="border-b hover:bg-gray-50">
                            <td className="px-3 py-2">{emp.name}</td>
                            <td className="px-3 py-2">{emp.certification}</td>
                            <td className="px-3 py-2 text-gray-600">{emp.earned_date ? new Date(emp.earned_date).toLocaleDateString() : "--"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="py-4 text-center text-gray-600">No core certified employees yet</div>
                )}
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
