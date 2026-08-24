import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, Users, Briefcase, RefreshCw, ChevronDown, CheckCircle } from "lucide-react";
import { Card, Button, StatusBadge } from "../components/ui";
import cx from "../utils/cx";
import { getExecutiveDashboard } from "../services/api/revenueTargets";
import { getAllCandidates } from "../services/api/candidates";
import { getAllJobs } from "../services/api/jobs";
import { getCEOFYProgress, getCEOFYSummary } from "../services/api/agents";

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

function ProgressBar({ current, target, pct }) {
  return (
    <div className="w-full">
      <div className="flex justify-between mb-2">
        <span className="text-sm text-gray-600">{current} / {target}</span>
        <span className="text-sm font-semibold text-gray-900">{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 90 ? "bg-green-500" : pct >= 70 ? "bg-blue-500" : "bg-amber-500"
          }`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

function MetricCard({ metric, status }) {
  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-gray-900">{metric.label}</h3>
            {status === "ON_TRACK" ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-amber-500" />
            )}
          </div>
          <ProgressBar
            current={metric.current}
            target={metric.target}
            pct={metric.progress_pct}
          />
          <div className="text-xs text-gray-500 mt-2">{metric.detail}</div>
        </div>
      </div>
    </Card>
  );
}

function RevenueByBUChart({ buMetrics }) {
  if (!buMetrics || buMetrics.length === 0) {
    return <div className="text-gray-500 text-sm">No revenue data by BU</div>;
  }

  const colors = ["bg-blue-500", "bg-purple-500", "bg-pink-500", "bg-orange-500", "bg-green-500"];

  return (
    <div className="space-y-3">
      {buMetrics.slice(0, 5).map((bu, idx) => {
        const maxRevenue = Math.max(...buMetrics.map(b => b.revenue_usd_cents || 0));
        const percentage = maxRevenue ? (bu.revenue_usd_cents / maxRevenue) * 100 : 0;

        return (
          <div key={idx}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium text-gray-900">{bu.name}</span>
              <span className="text-gray-600">{formatUsdCents(bu.revenue_usd_cents)}</span>
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

function RiskTiles({ risks }) {
  const defaultRisks = [
    { label: "Revenue Leakage", severity: "high", value: "0", icon: "💸" },
    { label: "Overdue Invoices", severity: "medium", value: "0", icon: "📋" },
    { label: "Bench Aging > 60d", severity: "medium", value: "0", icon: "⏳" },
    { label: "Unallocated Employees", severity: "low", value: "0", icon: "👤" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3">
      {defaultRisks.map((risk, idx) => {
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
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="bg-gradient-to-br from-blue-50 to-blue-100/50">
                  <div>
                    <div className="text-xs font-semibold text-blue-600 uppercase">FY Progress</div>
                    <div className="text-3xl font-bold text-blue-900 mt-2">{fySummary.fy_progress_pct.toFixed(0)}%</div>
                    <div className="text-xs text-blue-600 mt-2">Through the fiscal year</div>
                  </div>
                </Card>

                <Card className="bg-gradient-to-br from-green-50 to-green-100/50">
                  <div>
                    <div className="text-xs font-semibold text-green-600 uppercase">On Track</div>
                    <div className="text-3xl font-bold text-green-900 mt-2">{fySummary.on_track_count} / 7</div>
                    <div className="text-xs text-green-600 mt-2">Key metrics on plan</div>
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

              {/* Detailed Metrics */}
              {fyData && (
                <div>
                  <MetricCard
                    metric={{
                      label: "Headcount",
                      current: fyData.headcount.current,
                      target: fyData.headcount.target,
                      progress_pct: fyData.headcount.progress_pct,
                      detail: `Target: ${fyData.headcount.target} employees`
                    }}
                    status={fyData.headcount.status}
                  />
                  <MetricCard
                    metric={{
                      label: "Revenue",
                      current: (fyData.revenue.current_usd / 1000000).toFixed(1),
                      target: (fyData.revenue.target_usd / 1000000).toFixed(1),
                      progress_pct: fyData.revenue.progress_pct,
                      detail: `${fyData.revenue.progress_pct.toFixed(0)}% of annual target`
                    }}
                    status={fyData.revenue.status}
                  />
                  <MetricCard
                    metric={{
                      label: "New Logos",
                      current: fyData.new_logos.current,
                      target: fyData.new_logos.target,
                      progress_pct: fyData.new_logos.progress_pct,
                      detail: `Customer acquisition on track`
                    }}
                    status={fyData.new_logos.status}
                  />
                  <MetricCard
                    metric={{
                      label: "Engagement",
                      current: fyData.engagement.current_score.toFixed(0),
                      target: fyData.engagement.target_score,
                      progress_pct: fyData.engagement.progress_pct,
                      detail: "Opportunity pipeline health"
                    }}
                    status={fyData.engagement.status}
                  />
                  <MetricCard
                    metric={{
                      label: "Retention",
                      current: fyData.retention.current_pct.toFixed(0),
                      target: fyData.retention.target_pct,
                      progress_pct: fyData.retention.progress_pct,
                      detail: "Employee retention rate"
                    }}
                    status={fyData.retention.status}
                  />
                  <MetricCard
                    metric={{
                      label: "Utilization",
                      current: fyData.utilization.current_pct.toFixed(0),
                      target: fyData.utilization.target_pct,
                      progress_pct: fyData.utilization.progress_pct,
                      detail: "Billable hours vs available capacity"
                    }}
                    status={fyData.utilization.status}
                  />
                  <MetricCard
                    metric={{
                      label: "Margin",
                      current: fyData.margin.current_pct.toFixed(0),
                      target: fyData.margin.target_pct,
                      progress_pct: fyData.margin.progress_pct,
                      detail: "Gross margin percentage"
                    }}
                    status={fyData.margin.status}
                  />
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
