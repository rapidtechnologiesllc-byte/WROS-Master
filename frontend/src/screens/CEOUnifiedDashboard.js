import FinancialOutlookPanel from "../components/FinancialOutlookPanel";
import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, Users, Briefcase, RefreshCw, ChevronDown, CheckCircle } from "lucide-react";
import { Card, Button, Input, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import { getExecutiveDashboard } from "../services/api/revenueTargets";
import { getAllCandidates } from "../services/api/candidates";
import { getAllJobs } from "../services/api/jobs";
import { getCEOFYProgress, getCEOFYSummary, setFYStartMonth, setFYTarget } from "../services/api/agents";
import FYProgressPanel from "../components/FYProgressPanel";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function TabButton({ label, isActive, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cx(
        "px-4 py-2 font-semibold rounded-lg transition",
        isActive
          ? "bg-blue-600 text-white"
          : "bg-gray-200 text-gray-700 hover:bg-gray-300"
      )}
    >
      {label}
    </button>
  );
}

function BigNumberCard({ label, value, trend, unit = "" }) {
  return (
    <div className="rounded-lg border bg-gradient-to-br from-slate-50 to-slate-100/50 p-6">
      <div className="text-xs font-semibold text-slate-600 uppercase">{label}</div>
      <div className="mt-2 flex items-end gap-2">
        <div className="text-4xl font-bold text-gray-900">{value}</div>
        {unit && <div className="text-sm text-gray-600">{unit}</div>}
      </div>
      {trend && (
        <div className={`mt-2 text-sm font-medium ${trend.positive ? "text-emerald-600" : "text-rose-600"}`}>
          {trend.positive ? "↑" : "↓"} {trend.label}
        </div>
      )}
    </div>
  );
}

const formatMetricValue = (value, unit) => {
  if (value === null || value === undefined) return "--";
  if (unit === "USD") return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (unit === "%") return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
};

function ProgressBar({ current, target, pct, unit }) {
  return (
    <div className="w-full">
      <div className="flex justify-between mb-2">
        <span className="text-sm text-gray-600">
          {formatMetricValue(current, unit)} / {target === null ? "target not set" : formatMetricValue(target, unit)}
        </span>
        {pct !== null && <span className="text-sm font-semibold text-gray-900">{pct.toFixed(0)}%</span>}
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        {pct !== null && (
          <div
            className={`h-full rounded-full transition-all ${
              pct >= 90 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-amber-500"
            }`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        )}
      </div>
    </div>
  );
}

// One FY metric with its target; the target is edited in place
// (saved via PUT /goals/fy-targets/{metric}).
function MetricCard({ metric, onSaveTarget }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(metric.target ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    const number = Number(value);
    if (!number || number <= 0) {
      setError("Enter a positive number");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSaveTarget(metric.key, number);
      setEditing(false);
    } catch (err) {
      setError(err.message || "Could not save the target");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-gray-900">{metric.label}</h3>
            {metric.status === "ON_TRACK" && <CheckCircle className="h-5 w-5 text-green-500" />}
            {metric.status === "BEHIND" && <AlertTriangle className="h-5 w-5 text-amber-500" />}
            {metric.status === "NOT_SET" && (
              <span className="text-xs rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-gray-600">Target not set</span>
            )}
          </div>
          <ProgressBar current={metric.current} target={metric.target} pct={metric.progress_pct} unit={metric.unit} />
          <div className="text-xs text-gray-500 mt-2">{metric.detail}</div>
          {editing && (
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <div className="w-48">
                <Input label={`FY target (${metric.unit})`} type="number" value={value} onChange={setValue} disabled={saving} />
              </div>
              <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
              <Button
                variant="secondary"
                onClick={() => { setEditing(false); setValue(metric.target ?? ""); setError(null); }}
                disabled={saving}
              >
                Cancel
              </Button>
            </div>
          )}
          {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
        </div>
        {!editing && (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {metric.target === null ? "Set target" : "Edit target"}
          </Button>
        )}
      </div>
    </Card>
  );
}

function RevenueByBUChart({ buMetrics }) {
  if (!buMetrics || buMetrics.length === 0) {
    return (
      <div className="text-gray-500 text-sm">
        No business units yet -- add them in Users &amp; Access Control → Business Units.
      </div>
    );
  }

  const colors = ["bg-blue-500", "bg-purple-500", "bg-pink-500", "bg-orange-500", "bg-green-500"];

  return (
    <div className="space-y-3">
      {buMetrics.slice(0, 5).map((bu, idx) => {
        const maxRevenue = Math.max(...buMetrics.map(b => b.revenue_usd_cents || 0));
        const percentage = bu.target_usd_cents ? Math.min((bu.revenue_usd_cents / bu.target_usd_cents) * 100, 100) : (maxRevenue ? (bu.revenue_usd_cents / maxRevenue) * 100 : 0);

        return (
          <div key={idx}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium text-gray-900">{bu.name}</span>
              <span className="text-gray-600">
                {formatUsdCents(bu.revenue_usd_cents)}
                {bu.target_usd_cents ? ` / ${formatUsdCents(bu.target_usd_cents)} target` : ""}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`${colors[idx % colors.length]} h-2 rounded-full`}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PipelineFunnel({ candidates }) {
  const stages = {
    "NEW": { label: "New Leads", color: "bg-blue-100 text-blue-700" },
    "SHORTLISTED": { label: "Shortlisted", color: "bg-blue-200 text-blue-800" },
    "INTERVIEW": { label: "In Interview", color: "bg-purple-100 text-purple-700" },
    "OFFER": { label: "Offer Made", color: "bg-amber-100 text-amber-700" },
    "HIRED": { label: "Hired", color: "bg-emerald-100 text-emerald-700" },
  };

  const stageCounts = {};
  Object.keys(stages).forEach(stage => {
    stageCounts[stage] = (candidates || []).filter(c => c.status === stage).length;
  });

  const maxCount = Math.max(...Object.values(stageCounts), 1);

  return (
    <div className="space-y-3">
      {Object.entries(stages).map(([key, stage]) => {
        const count = stageCounts[key] || 0;
        const width = (count / maxCount) * 100;

        return (
          <div key={key}>
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium text-gray-900">{stage.label}</span>
              <span className="font-bold">{count}</span>
            </div>
            <div className={`h-8 rounded ${stage.color} flex items-center justify-center text-xs font-semibold`}
              style={{ width: `${Math.max(width, 10)}%` }}>
              {count > 0 && count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const RISK_ICONS = { revenue_leakage: "💸", overdue_invoices: "📋", bench_aging: "⏳", unallocated: "👤" };

function RiskTiles({ risks }) {
  if (!risks || risks.length === 0) {
    return <div className="text-gray-500 text-sm">Risk data unavailable</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {risks.map((r, idx) => {
        const risk = { ...r, icon: RISK_ICONS[r.key] || "⚠️" };
        const bgColor =
          risk.severity === "high" ? "bg-rose-50 border-rose-200" :
          risk.severity === "medium" ? "bg-amber-50 border-amber-200" :
          "bg-blue-50 border-blue-200";

        const textColor =
          risk.severity === "high" ? "text-rose-700" :
          risk.severity === "medium" ? "text-amber-700" :
          "text-blue-700";

        return (
          <div key={idx} className={`rounded-lg border ${bgColor} p-3`}>
            <div className="text-2xl mb-1">{risk.icon}</div>
            <div className={`text-xs font-semibold ${textColor}`}>{risk.label}</div>
            <div className="text-lg font-bold text-gray-900 mt-1">{risk.value}</div>
            {risk.detail && <div className="text-[11px] text-gray-500">{risk.detail}</div>}
          </div>
        );
      })}
    </div>
  );
}

function CapacityUtilization({ utilization }) {
  const util = utilization || 0;
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - (util / 100) * circumference;

  const color = util >= 100 ? "#dc2626" : util >= 80 ? "#f59e0b" : "#10b981";

  return (
    <div className="flex flex-col items-center gap-4">
      <svg width="120" height="120" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="60" cy="60" r="45" fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle
          cx="60"
          cy="60"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
        <text
          x="60"
          y="65"
          textAnchor="middle"
          fontSize="24"
          fontWeight="bold"
          fill="#1f2937"
        >
          {util}%
        </text>
      </svg>
      <div className="text-sm text-gray-600 text-center">
        Team Utilization
        <div className="font-semibold text-gray-900">
          {util >= 100 ? "Over Capacity" : util >= 80 ? "High" : "Optimal"}
        </div>
      </div>
    </div>
  );
}

export default function CEOUnifiedDashboard() {
  const [activeTab, setActiveTab] = useState("fy-progress"); // "fy-progress" or "executive"
  const [fyData, setFyData] = useState(null);
  const [fySummary, setFySummary] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDashboard();
  }, []);

  const refreshFY = async () => {
    const [progress, summary] = await Promise.all([getCEOFYProgress(), getCEOFYSummary()]);
    setFyData(progress);
    setFySummary(summary);
  };

  const handleSaveTarget = async (metricKey, target) => {
    await setFYTarget(metricKey, target, fyData?.fy_year);
    await refreshFY();
  };

  const handleChangeFYStart = async (startMonth) => {
    await setFYStartMonth(startMonth);
    await refreshFY();
  };

  const loadDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      const [fyProgressData, fySummaryData, executiveData, candidatesData, jobsData] = await Promise.all([
        getCEOFYProgress().catch(() => null),
        getCEOFYSummary().catch(() => null),
        getExecutiveDashboard().catch(() => null),
        getAllCandidates().catch(() => ({ candidates: [] })),
        getAllJobs().catch(() => ({ jobs: [] })),
      ]);

      setFyData(fyProgressData);
      setFySummary(fySummaryData);
      setDashboard(executiveData);
      setCandidates(candidatesData?.candidates || []);
      setJobs(jobsData?.jobs || []);
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  const openPositions = (jobs || []).filter(j => j.status !== "FILLED" && j.status !== "CANCELLED").length;

  return (
    <div className="space-y-6 p-6">
      {/* Header with Tab Navigation */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">CEO Dashboard</h1>
            <p className="mt-1 text-gray-600">Unified view of FY progress and executive metrics</p>
          </div>
          <Button variant="ghost" onClick={loadDashboard} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2">
          <TabButton
            label="FY Progress"
            isActive={activeTab === "fy-progress"}
            onClick={() => setActiveTab("fy-progress")}
          />
          <TabButton
            label="Executive Metrics"
            isActive={activeTab === "executive"}
            onClick={() => setActiveTab("executive")}
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 flex gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-600 flex-shrink-0" />
          <div className="text-sm text-rose-700">{error}</div>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading CEO dashboard...</div>
      ) : (
        <>
          {/* FY PROGRESS TAB */}
          {activeTab === "fy-progress" && fySummary && (
            <div className="space-y-6">
              {/* Executive Summary Cards */}
              <FinancialOutlookPanel title="Org revenue & expense: plan vs actual" groupBy="partner" />
              <FYProgressPanel fyData={fyData} onChangeStartMonth={handleChangeFYStart} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                <Card className="bg-gradient-to-br from-green-50 to-green-100/50">
                  <div>
                    <div className="text-xs font-semibold text-green-600 uppercase">On Track</div>
                    <div className="text-3xl font-bold text-green-900 mt-2">
                      {fySummary.targets_set ? `${fySummary.on_track_count} / ${fySummary.targets_set}` : "--"}
                    </div>
                    <div className="text-xs text-green-600 mt-2">
                      {fySummary.targets_set < fySummary.metrics_total
                        ? `Metrics with targets on plan (${fySummary.metrics_total - fySummary.targets_set} targets not set)`
                        : "Key metrics on plan"}
                    </div>
                  </div>
                </Card>

                <Card className="bg-gradient-to-br from-amber-50 to-amber-100/50">
                  <div>
                    <div className="text-xs font-semibold text-amber-600 uppercase">Behind</div>
                    <div className="text-3xl font-bold text-amber-900 mt-2">{fySummary.behind_count}</div>
                    <div className="text-xs text-amber-600 mt-2">Needs attention</div>
                  </div>
                </Card>
              </div>

              {/* Key Metrics Summary */}
              <Card title="Key Metrics" className="mb-6">
                <div className="text-sm text-gray-600 mb-4">{fySummary.headline}</div>
                <div className="space-y-2">
                  {Object.entries(fySummary.key_metrics).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-gray-600 capitalize">{key}</span>
                      <span className="font-semibold text-gray-900">{value}</span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Detailed Metrics -- targets are set/edited on each card */}
              {fyData?.metrics && (
                <div>
                  {fyData.metrics.map((m) => (
                    <MetricCard key={`${m.key}-${m.target}`} metric={m} onSaveTarget={handleSaveTarget} />
                  ))}
                </div>
              )}

              {/* CEO Priorities */}
              {fySummary.priorities && (
                <Card title="CEO Priorities" className="mt-6">
                  <div className="space-y-4">
                    {fySummary.priorities.map((priority, i) => (
                      <div key={i} className="flex gap-4 pb-4 border-b last:border-0">
                        <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center font-semibold text-blue-600">
                          {priority.rank}
                        </div>
                        <div className="flex-1">
                          <div className="font-semibold text-gray-900">{priority.metric}</div>
                          <div className="text-sm text-gray-600 mt-1">{priority.gap}</div>
                          <div className="text-sm font-medium text-blue-600 mt-1">{priority.action}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* EXECUTIVE METRICS TAB */}
          {activeTab === "executive" && dashboard && (
            <div className="space-y-6">
              {/* Key Metrics */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <BigNumberCard
                  label="TOTAL REVENUE"
                  value={formatUsdCents(dashboard?.total_revenue_usd_cents)}
                  unit="YTD"
                />
                <BigNumberCard
                  label="TEAM CAPACITY"
                  value={dashboard?.team_capacity_utilization_pct ? `${dashboard.team_capacity_utilization_pct}%` : "—"}
                />
                <BigNumberCard
                  label="OPEN POSITIONS"
                  value={openPositions}
                  unit={openPositions === 1 ? "role" : "roles"}
                />
              </div>

              {/* Revenue by BU & Capacity Gauge */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Card className="p-6">
                  <h3 className="font-semibold mb-4">REVENUE BY BUSINESS UNIT</h3>
                  <RevenueByBUChart buMetrics={dashboard?.bu_metrics} />
                </Card>
                <Card className="p-6 flex items-center justify-center">
                  <CapacityUtilization utilization={dashboard?.team_capacity_utilization_pct} />
                </Card>
              </div>

              {/* Pipeline & Risks */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Card className="p-6">
                  <h3 className="font-semibold mb-4">CANDIDATE PIPELINE (Funnel)</h3>
                  <PipelineFunnel candidates={candidates} />
                </Card>
                <Card className="p-6">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    TOP RISKS
                  </h3>
                  <RiskTiles risks={dashboard?.risks} />
                </Card>
              </div>

              {/* Pipeline Coverage */}
              {dashboard?.pipeline_coverage && (
                <Card className="p-6 bg-gradient-to-r from-indigo-50 to-blue-50">
                  <h3 className="font-semibold mb-2">PIPELINE COVERAGE RATIO</h3>
                  <div className="text-3xl font-bold text-gray-900">{dashboard.pipeline_coverage}x</div>
                  <p className="mt-1 text-sm text-gray-600">
                    Open pipeline covers {dashboard.pipeline_coverage}x of annual revenue target
                  </p>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
