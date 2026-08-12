// DEFECT-6 & 7: Role-based dashboards (Partner/BU Head, CEO/Executive)
// Common dashboard framework for role-specific metrics

import { useEffect, useState } from "react";
import { BarChart, PieChart, Gauge, TrendingUp, Users, DollarSign, AlertTriangle } from "lucide-react";
import { Card, Button } from "../components/ui";

function MetricCard({ label, value, unit, icon: Icon, trend, color = "blue" }) {
  const colorClasses = {
    blue: "bg-blue-50 text-blue-900 border-blue-200",
    green: "bg-green-50 text-green-900 border-green-200",
    red: "bg-red-50 text-red-900 border-red-200",
    yellow: "bg-yellow-50 text-yellow-900 border-yellow-200",
  };

  return (
    <Card className={`p-4 border ${colorClasses[color] || colorClasses.blue}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium opacity-75">{label}</div>
          <div className="mt-1 text-3xl font-bold">{value}</div>
          {unit && <div className="text-xs opacity-50 mt-1">{unit}</div>}
          {trend && <div className="text-xs mt-2 font-semibold">{trend}</div>}
        </div>
        <div className="p-2 bg-white bg-opacity-50 rounded">
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </Card>
  );
}

function ChartPlaceholder({ title, description }) {
  return (
    <Card className="p-8 text-center">
      <div className="text-gray-400">
        <TrendingUp className="h-12 w-12 mx-auto mb-2 opacity-50" />
        <h3 className="font-semibold text-gray-700">{title}</h3>
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      </div>
    </Card>
  );
}

export function PartnerBUDashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    // TODO: Load from API
    // GET /dashboards/partner-bu-head
    setLoading(false);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-600">Partner / BU Head Overview</p>
      </div>

      {/* Metrics Row 1 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Revenue (This Month)"
          value="$485K"
          unit="+12% vs last month"
          icon={DollarSign}
          color="green"
        />
        <MetricCard
          label="Capacity Utilized"
          value="78%"
          unit="45 of 58 employees"
          icon={Users}
          color="blue"
        />
        <MetricCard
          label="Top Client"
          value="Guidewire Inc."
          unit="$125K revenue"
          icon={TrendingUp}
          color="blue"
        />
        <MetricCard
          label="Timesheets Pending"
          value="7"
          unit="Due by 5 PM"
          icon={AlertTriangle}
          color="yellow"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartPlaceholder
          title="Revenue by Month"
          description="Bar chart showing revenue trend for current BU"
        />
        <ChartPlaceholder
          title="Top 5 Clients by Revenue"
          description="Pie chart showing client contribution"
        />
      </div>

      {/* Heatmap & Pending Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartPlaceholder
          title="Team Utilization Heatmap"
          description="Color-coded availability (red=busy, green=available)"
        />
        <Card className="p-4">
          <h3 className="font-semibold mb-3">Pending Items</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between p-2 bg-yellow-50 rounded">
              <span>Timesheets Pending Approval</span>
              <span className="font-semibold text-yellow-900">7</span>
            </div>
            <div className="flex justify-between p-2 bg-blue-50 rounded">
              <span>Expenses Pending Review</span>
              <span className="font-semibold text-blue-900">3</span>
            </div>
            <div className="flex justify-between p-2 bg-purple-50 rounded">
              <span>Invoices Awaiting Payment</span>
              <span className="font-semibold text-purple-900">2</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export function CEODashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    // TODO: Load from API
    // GET /dashboards/executive
    setLoading(false);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Executive Dashboard</h1>
        <p className="text-gray-600">Organization-wide performance metrics</p>
      </div>

      {/* Big Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          label="Total Revenue (YTD)"
          value="$2.4M"
          unit="+18% vs last year"
          icon={DollarSign}
          color="green"
        />
        <MetricCard
          label="Team Capacity"
          value="82%"
          unit="312 of 380 allocated"
          icon={Users}
          color="blue"
        />
        <MetricCard
          label="Active Positions"
          value="24"
          unit="Across 4 BUs"
          icon={TrendingUp}
          color="blue"
        />
      </div>

      {/* Executive Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartPlaceholder
          title="Revenue by Business Unit"
          description="Stacked bar chart for Q3 2026"
        />
        <ChartPlaceholder
          title="Candidate Pipeline Funnel"
          description="Funnel showing qual → offer → hire progression"
        />
      </div>

      {/* Risks & Strategic Metrics */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4">Top Risks & Alerts</h3>
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-3 bg-red-50 rounded border border-red-200">
            <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-red-900">Revenue Leakage Detected</div>
              <div className="text-sm text-red-700">$18K in unbilled hours across projects</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-yellow-50 rounded border border-yellow-200">
            <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-yellow-900">Overdue Invoices</div>
              <div className="text-sm text-yellow-700">3 invoices > 60 days past due ($42K)</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function RoleDashboardRouter() {
  // Determines which dashboard to show based on user role
  // TODO: Use useAuth() to determine role
  // return role === "PARTNER" || role === "BU_HEAD" ? <PartnerBUDashboard /> : <CEODashboard />
  return <CEODashboard />;
}
