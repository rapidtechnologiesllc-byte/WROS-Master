// DEFECT-7: CEO / Super User Executive Dashboard
// Metrics: Total revenue, revenue by BU (stacked bar), team capacity utilization %,
// candidates in pipeline (funnel), open positions, top risks

import { useEffect, useState } from "react";
import { TrendingUp, AlertTriangle, Users, Briefcase, RefreshCw } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getExecutiveDashboard } from "../services/api/revenueTargets";
import { getAllCandidates } from "../services/api/candidates";
import { getAllJobs } from "../services/api/jobs";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

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

export default function CEOExecutiveDashboardScreen() {
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
      const [dashboardData, candidatesData, jobsData] = await Promise.all([
        getExecutiveDashboard(),
        getAllCandidates().catch(() => ({ candidates: [] })),
        getAllJobs().catch(() => ({ jobs: [] })),
      ]);

      setDashboard(dashboardData);
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
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Executive Dashboard</h1>
            <p className="mt-1 text-gray-600">Company-wide metrics and strategic risks</p>
          </div>
          <Button variant="ghost" onClick={loadDashboard} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 flex gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-600 flex-shrink-0" />
          <div className="text-sm text-rose-700">{error}</div>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading executive dashboard...</div>
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
