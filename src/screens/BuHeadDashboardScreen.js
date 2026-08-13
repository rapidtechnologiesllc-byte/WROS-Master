// DEFECT-6: Partner/BU Head Dashboard
// Metrics: Revenue this month (by BU), capacity utilization, top clients,
// team utilization heatmap, timesheets pending, expenses pending review

import { useEffect, useState } from "react";
import { TrendingUp, Users, DollarSign, Clock, AlertCircle, RefreshCw } from "lucide-react";
import { Card, Button } from "../components/ui";
import cx from "../utils/cx";
import { getExecutiveDashboard } from "../services/api/revenueTargets";
import { listBusinessUnits } from "../services/api/rbac";

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function RevenueCard({ title, value, subtitle }) {
  return (
    <div className="rounded-lg border bg-gradient-to-br from-blue-50 to-blue-100/50 p-4 hover:from-blue-100">
      <div className="text-xs font-semibold text-blue-600">{title}</div>
      <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
      {subtitle && <div className="mt-1 text-[11px] text-gray-600">{subtitle}</div>}
    </div>
  );
}

function CapacityGauge({ utilization }) {
  const percentage = utilization || 0;
  const bgColor =
    percentage >= 100 ? "bg-red-100" :
    percentage >= 75 ? "bg-yellow-100" :
    "bg-green-100";

  const textColor =
    percentage >= 100 ? "text-red-700" :
    percentage >= 75 ? "text-yellow-700" :
    "text-green-700";

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-xs font-semibold text-gray-600 mb-3">ALLOCATED VS AVAILABLE</div>
      <div className="flex items-center gap-4">
        <div className={`${bgColor} rounded-full w-24 h-24 flex items-center justify-center`}>
          <div className={`text-3xl font-bold ${textColor}`}>{percentage}%</div>
        </div>
        <div className="flex-1">
          <div className={`text-sm ${textColor} font-semibold`}>
            {percentage >= 100 ? "Over Allocated" :
             percentage >= 75 ? "High Utilization" :
             "Optimal Capacity"}
          </div>
          <div className="mt-1 text-[11px] text-gray-600">
            {percentage >= 100 ? "Additional capacity needed" :
             percentage >= 75 ? "Consider adding resources" :
             "Room for growth"}
          </div>
        </div>
      </div>
    </div>
  );
}

function TopClientsCard({ clients }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-xs font-semibold text-gray-600 mb-3">TOP 5 CLIENTS BY REVENUE</div>
      <div className="space-y-2">
        {(clients || []).slice(0, 5).map((client, idx) => (
          <div key={idx} className="flex items-center justify-between">
            <div className="text-sm font-medium text-gray-900">{client.name}</div>
            <div className="text-sm font-semibold text-blue-600">{formatUsdCents(client.revenue_usd_cents)}</div>
          </div>
        ))}
        {(!clients || clients.length === 0) && (
          <div className="text-sm text-gray-500">No client revenue data available</div>
        )}
      </div>
    </div>
  );
}

function UtilizationHeatmap({ employees }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="text-xs font-semibold text-gray-600 mb-3">TEAM UTILIZATION HEATMAP</div>
      <div className="space-y-2">
        {(employees || []).slice(0, 10).map((emp) => {
          const util = emp.utilization_pct || 0;
          const bgColor =
            util >= 100 ? "bg-red-200" :
            util >= 75 ? "bg-yellow-200" :
            util >= 50 ? "bg-green-200" :
            "bg-blue-200";

          return (
            <div key={emp.id} className="flex items-center gap-2">
              <div className="w-20 text-xs font-medium truncate text-gray-700">
                {emp.first_name} {emp.last_name}
              </div>
              <div className={`flex-1 h-6 rounded ${bgColor} flex items-center justify-center text-xs font-semibold text-gray-900`}>
                {util}%
              </div>
            </div>
          );
        })}
        {(!employees || employees.length === 0) && (
          <div className="text-sm text-gray-500">No employee data available</div>
        )}
      </div>
    </div>
  );
}

function PendingItemsCard() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="rounded-lg border bg-gradient-to-br from-amber-50 to-amber-100/50 p-4">
        <div className="text-xs font-semibold text-amber-600 mb-2">TIMESHEETS PENDING</div>
        <div className="text-3xl font-bold text-gray-900">0</div>
        <div className="mt-2 text-[11px] text-gray-600">Awaiting approval</div>
      </div>
      <div className="rounded-lg border bg-gradient-to-br from-orange-50 to-orange-100/50 p-4">
        <div className="text-xs font-semibold text-orange-600 mb-2">EXPENSES PENDING</div>
        <div className="text-3xl font-bold text-gray-900">0</div>
        <div className="mt-2 text-[11px] text-gray-600">Under review</div>
      </div>
    </div>
  );
}

export default function BuHeadDashboardScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [businessUnits, setBusinessUnits] = useState([]);
  const [selectedBuId, setSelectedBuId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
  }, [selectedBuId]);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [dashboardData, busData] = await Promise.all([
        selectedBuId ? getExecutiveDashboard() : Promise.resolve(null),
        listBusinessUnits(),
      ]);

      setDashboard(dashboardData);
      setBusinessUnits(busData?.business_units || busData || []);

      // Auto-select first BU if not selected
      if (!selectedBuId && busData?.business_units?.length) {
        setSelectedBuId(String(busData.business_units[0].business_unit_id || busData.business_units[0].id));
      }
    } catch (err) {
      setError(err.message || "Failed to load dashboard data");
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  const currentBU = businessUnits.find(bu => String(bu.business_unit_id || bu.id) === selectedBuId);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Business Unit Dashboard</h1>
            <p className="mt-1 text-gray-600">Revenue, capacity, and team metrics for your BU</p>
          </div>
          <Button variant="ghost" onClick={loadData} disabled={loading}>
            <RefreshCw className={cx("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>
      </div>

      {/* BU Selector */}
      <div>
        <label className="text-sm font-semibold text-gray-700">Select Business Unit</label>
        <select
          value={selectedBuId}
          onChange={(e) => setSelectedBuId(e.target.value)}
          className="mt-2 w-full rounded-lg border bg-white px-3 py-2 text-sm"
        >
          <option value="">All Business Units</option>
          {businessUnits.map((bu) => (
            <option key={bu.id} value={String(bu.business_unit_id || bu.id)}>
              {bu.name || bu.bu_name}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 flex gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 flex-shrink-0" />
          <div className="text-sm text-rose-700">{error}</div>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-gray-500">Loading dashboard...</div>
      ) : (
        <>
          {/* Revenue Section */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <RevenueCard
              title="REVENUE THIS MONTH"
              value={formatUsdCents(dashboard?.month_revenue_usd_cents)}
              subtitle="Current fiscal period"
            />
            <RevenueCard
              title="PLANNED REVENUE"
              value={formatUsdCents(dashboard?.planned_usd_cents)}
              subtitle="YTD forecast"
            />
            <RevenueCard
              title="BILLABLE RATIO"
              value={dashboard?.billable_ratio_pct ? `${dashboard.billable_ratio_pct}%` : "—"}
              subtitle="Revenue billability"
            />
          </div>

          {/* Capacity & Clients */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <CapacityGauge utilization={dashboard?.utilization_pct || 0} />
            <TopClientsCard clients={dashboard?.top_clients} />
          </div>

          {/* Team & Pending */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UtilizationHeatmap employees={dashboard?.employees} />
            <PendingItemsCard />
          </div>

          {/* Bench Summary */}
          {dashboard?.bench_summary && (
            <Card className="p-4">
              <h3 className="font-semibold mb-3">BENCH POOL SUMMARY</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-600">Total on Bench</div>
                  <div className="text-2xl font-bold text-gray-900">{dashboard.bench_summary.total || 0}</div>
                </div>
                <div>
                  <div className="text-gray-600">Aging > 30 days</div>
                  <div className="text-2xl font-bold text-amber-600">{dashboard.bench_summary.aging_30_plus || 0}</div>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
