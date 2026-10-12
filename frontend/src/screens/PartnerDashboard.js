import { Fragment, useEffect, useState } from "react";
import { Briefcase, Users, Award, TrendingUp, X, AlertTriangle } from "lucide-react";
import { Card, Button } from "../components/ui";
import { apiRequest } from "../services/api/client";

// Partner dashboard: the business units a partner owns, across every company
// they run in (BX-US, BX-IN, ...). A partner sees their own; Admin/CEO pick one.
const METRICS = [
  { key: "revenue", label: "Revenue", usd: true },
  { key: "headcount", label: "Billable headcount" },
  { key: "new_logos", label: "New logos" },
];

const fmt = (value, usd) => {
  if (value === null || value === undefined) return "--";
  const n = Number(value);
  if (!usd) return n.toLocaleString();
  return Math.abs(n) >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

function MetricCell({ cell, usd }) {
  if (!cell) return <span className="text-gray-400">--</span>;
  const pct = cell.progress_pct;
  return (
    <div>
      <div className="font-semibold text-gray-900">
        {fmt(cell.actual, usd)} <span className="text-xs font-normal text-gray-500">/ {cell.target ? fmt(cell.target, usd) : "no target"}</span>
      </div>
      {pct !== null && pct !== undefined && (
        <div className="mt-1 h-1.5 w-full rounded bg-gray-100">
          <div className={`h-1.5 rounded ${pct >= 100 ? "bg-green-500" : pct >= 60 ? "bg-blue-500" : "bg-amber-500"}`}
               style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
      )}
    </div>
  );
}

export default function PartnerDashboard() {
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [partnerChoices, setPartnerChoices] = useState(null);
  const [partnerId, setPartnerId] = useState("");
  const [buId, setBuId] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const qs = new URLSearchParams();
        if (partnerId) qs.set("partner_user_id", partnerId);
        if (buId) qs.set("business_unit_id", buId);
        const { data } = await apiRequest(`/dashboards/partner${qs.toString() ? `?${qs}` : ""}`, { method: "GET" });
        if (data?.status === "needs_partner") {
          setPartnerChoices(data.partners || []);
          setResult(null);
          return;
        }
        if (data?.partners) setPartnerChoices(data.partners);
        setResult(data);
      } catch (err) {
        setActionError(`Failed to load the partner dashboard: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [partnerId, buId]);

  const picker = partnerChoices ? (
    <div className="flex items-center gap-3">
      <label className="text-sm font-medium text-gray-700" htmlFor="partner-picker">Partner</label>
      <select
        id="partner-picker"
        value={partnerId || result?.partner?.user_id || ""}
        onChange={(e) => { setPartnerId(e.target.value); setBuId(""); }}
        className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
      >
        <option value="">Select a partner</option>
        {partnerChoices.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      {partnerChoices.length === 0 && (
        <span className="text-sm text-amber-700">No partners yet: give a user the Partner role and set them as Partner on a business unit.</span>
      )}
    </div>
  ) : null;

  if (loading && !result) return <div className="p-6 text-center text-gray-500">Loading dashboard...</div>;
  if (!result) {
    return (
      <div className="p-6 space-y-4 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900">Partner Dashboard</h1>
        {actionError && <div className="text-red-700 text-sm">{actionError}</div>}
        {picker || <div className="text-center text-gray-500">No data available</div>}
      </div>
    );
  }

  const dashboard = result.data || {};
  const {
    current_demand,
    pre_onboarding_pipeline,
    certifications,
    buddy_program,
    core_certified_employees
  } = dashboard;

  return (
    <div className="space-y-6 p-6 max-w-6xl mx-auto">
      {/* Error Banner */}
      {actionError && (
        <div className="mb-6 border border-red-200 bg-red-50 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-red-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <span className="text-red-800">{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-red-600 hover:text-red-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Partner Dashboard</h1>
          <div className="text-sm text-gray-600">
            {result.partner?.name} · {result.business_units.length} business unit(s) · {result.fy_label}
          </div>
        </div>
        {picker}
      </div>

      {result.business_units.length === 0 ? (
        <Card>
          <div className="text-sm text-gray-600">
            {result.partner?.name} is not the partner of any business unit yet. Set the Partner on each business unit in
            Users &amp; Access Control → Business Units.
          </div>
        </Card>
      ) : (
        <Card title="FY targets vs actuals">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-gray-500">
                  <th className="py-2 px-3">Company / Business unit</th>
                  {METRICS.map((m) => <th key={m.key} className="py-2 px-3">{m.label}</th>)}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b bg-gray-50">
                  <td className="py-2 px-3 font-bold">All companies</td>
                  {METRICS.map((m) => <td key={m.key} className="py-2 px-3"><MetricCell cell={result.totals[m.key]} usd={m.usd} /></td>)}
                </tr>
                {result.by_company.map((c) => (
                  <Fragment key={c.company_id}>
                    <tr className="border-b">
                      <td className="py-2 px-3 font-semibold">{c.company}</td>
                      {METRICS.map((m) => <td key={m.key} className="py-2 px-3"><MetricCell cell={c.metrics[m.key]} usd={m.usd} /></td>)}
                    </tr>
                    {c.business_units.map((bu) => (
                      <tr key={`${c.company_id}:${bu.bu_id}`} className="border-b">
                        <td className="py-2 px-3 pl-8 text-gray-700">
                          {bu.name}
                          {bu.head && <span className="ml-2 text-xs text-gray-500">Head: {bu.head}</span>}
                        </td>
                        {METRICS.map((m) => <td key={m.key} className="py-2 px-3"><MetricCell cell={bu.metrics[m.key]} usd={m.usd} /></td>)}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-gray-500">Targets are set on Executive → Goals &amp; Revenue.</p>
        </Card>
      )}

      {result.business_units.length > 0 && (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-gray-700" htmlFor="bu-filter">Operations for</label>
          <select
            id="bu-filter"
            value={buId}
            onChange={(e) => setBuId(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">All my business units</option>
            {result.business_units.map((bu) => <option key={bu.id} value={bu.id}>{bu.name}</option>)}
          </select>
        </div>
      )}

      {result.data && (<>
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Open Positions</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{current_demand?.open_positions || 0}</div>
            </div>
            <Briefcase className="h-6 w-6 text-blue-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Pre-Onboarding</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{pre_onboarding_pipeline?.in_pre_onboarding || 0}</div>
            </div>
            <TrendingUp className="h-6 w-6 text-purple-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Certified</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{certifications?.total_active || 0}</div>
            </div>
            <Award className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Buddy Program</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{buddy_program?.total_in_program || 0}</div>
            </div>
            <Users className="h-6 w-6 text-indigo-500" />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Core Certified</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{core_certified_employees?.length || 0}</div>
            </div>
            <Award className="h-6 w-6 text-yellow-500" />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Demand */}
        <Card title="Current Demand">
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
              <span className="font-semibold">Open Positions</span>
              <span className="text-2xl font-bold text-blue-600">{current_demand?.open_positions || 0}</span>
            </div>
            <div className="text-sm text-gray-600">
              Positions open for recruitment in {buId ? "this business unit" : "your business units"}
            </div>
            <Button className="w-full">View Open Positions</Button>
          </div>
        </Card>

        {/* Pre-Onboarding Pipeline */}
        <Card title="Pre-Onboarding Pipeline">
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-purple-50 rounded-lg">
              <span className="font-semibold">In Pipeline</span>
              <span className="text-2xl font-bold text-purple-600">{pre_onboarding_pipeline?.in_pre_onboarding || 0}</span>
            </div>
            <div className="text-sm text-gray-600">
              Candidates ready for onboarding
            </div>
            <Button className="w-full">Start Onboarding</Button>
          </div>
        </Card>

        {/* Certifications */}
        <Card title="Certification Status">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Total Certified</span>
              <span className="font-bold">{certifications?.total_active || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-orange-600">Expiring Soon</span>
              <span className="font-bold text-orange-600">{certifications?.expiring_within_30_days || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-600">Expired</span>
              <span className="font-bold text-red-600">{certifications?.already_expired || 0}</span>
            </div>
            {certifications?.by_level && (
              <div className="mt-3 pt-3 border-t space-y-1">
                {Object.entries(certifications.by_level).map(([level, count]) => (
                  <div key={level} className="flex justify-between text-sm">
                    <span>{level}</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Buddy Program */}
        <Card title="Buddy Program Status">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>In Program</span>
              <span className="font-bold">{buddy_program?.total_in_program || 0}</span>
            </div>
            <div className="flex justify-between text-green-600">
              <span>On Track</span>
              <span className="font-bold">{buddy_program?.on_track || 0}</span>
            </div>
            <div className="flex justify-between text-orange-600">
              <span>At Risk</span>
              <span className="font-bold">{buddy_program?.at_risk || 0}</span>
            </div>
            <div className="flex justify-between text-green-600">
              <span>Completed This Month</span>
              <span className="font-bold">{buddy_program?.completed_this_month || 0}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Core Certified Employees */}
      <Card title="Core Certified Employees">
        {core_certified_employees && core_certified_employees.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 font-semibold">Employee</th>
                  <th className="text-left py-2 px-3 font-semibold">Certification</th>
                  <th className="text-left py-2 px-3 font-semibold">Earned Date</th>
                </tr>
              </thead>
              <tbody>
                {core_certified_employees.map((emp, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50">
                    <td className="py-2 px-3">{emp.name}</td>
                    <td className="py-2 px-3">{emp.certification}</td>
                    <td className="py-2 px-3 text-sm text-gray-600">
                      {emp.earned_date ? new Date(emp.earned_date).toLocaleDateString() : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-600 py-4">No core certified employees yet</div>
        )}
      </Card>
      </>)}
    </div>
  );
}
