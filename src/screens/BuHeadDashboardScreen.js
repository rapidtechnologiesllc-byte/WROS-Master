import { useEffect, useState } from "react";
import { Users, TrendingUp, DollarSign, AlertCircle, Briefcase } from "lucide-react";
import { Card } from "../components/ui";
import { apiRequest } from "../services/api/client";

export default function BUHeadDashboardScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError("");
    try {
      const [dashRes, teamRes] = await Promise.all([
        apiRequest("/dashboards/bu-head/summary", { method: "GET" }),
        apiRequest("/dashboards/bu-head/team", { method: "GET" })
      ]);

      setDashboard(dashRes.data?.data);
      setTeam(teamRes.data?.data?.team_members || []);
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-6 text-center text-gray-500">Loading BU dashboard...</div>;
  if (error) return <div className="p-6 text-center text-red-600">Error: {error}</div>;
  if (!dashboard) return <div className="p-6 text-center text-gray-500">No data available</div>;

  const { team_size, revenue, delivery } = dashboard;
  const formatCurrency = (value) => `$${(value / 1000).toFixed(1)}k`;

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{dashboard.bu_name} - Business Unit Dashboard</h1>
        <p className="text-gray-600 mt-1">Complete visibility of delivery, team, and revenue</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Team Utilization */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Team Utilization</div>
              <div className="text-3xl font-bold text-blue-600 mt-2">{team_size.utilization_percent}%</div>
              <div className="text-xs text-gray-600 mt-1">{team_size.utilized}/{team_size.total} in projects</div>
            </div>
            <Users className="h-6 w-6 text-blue-500" />
          </div>
        </Card>

        {/* Revenue MTD */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Revenue MTD</div>
              <div className="text-3xl font-bold text-green-600 mt-2">{formatCurrency(revenue.mtd_usd)}</div>
              <div className="text-xs text-gray-600 mt-1">Month to date</div>
            </div>
            <DollarSign className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        {/* ARN */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Annual Run Rate</div>
              <div className="text-3xl font-bold text-green-600 mt-2">{formatCurrency(revenue.arn_usd)}</div>
              <div className="text-xs text-gray-600 mt-1">Projected annual</div>
            </div>
            <TrendingUp className="h-6 w-6 text-green-500" />
          </div>
        </Card>

        {/* Bench Cost */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Bench Cost/Day</div>
              <div className="text-3xl font-bold text-orange-600 mt-2">{formatCurrency(revenue.bench_cost_daily_usd)}</div>
              <div className="text-xs text-gray-600 mt-1">{team_size.bench} idle employees</div>
            </div>
            <AlertCircle className="h-6 w-6 text-orange-500" />
          </div>
        </Card>
      </div>

      {/* Team Size Breakdown */}
      <Card title="Team Summary">
        <div className="grid grid-cols-3 gap-8">
          <div className="text-center">
            <div className="text-4xl font-bold text-blue-600">{team_size.total}</div>
            <div className="text-sm text-gray-600 mt-2">Total Team Members</div>
          </div>
          <div className="text-center">
            <div className="text-4xl font-bold text-green-600">{team_size.utilized}</div>
            <div className="text-sm text-gray-600 mt-2">Allocated to Projects</div>
          </div>
          <div className="text-center">
            <div className="text-4xl font-bold text-orange-600">{team_size.bench}</div>
            <div className="text-sm text-gray-600 mt-2">On Bench</div>
          </div>
        </div>
      </Card>

      {/* Active Projects & Allocations */}
      {delivery.project_allocations.length > 0 && (
        <Card title="Active Projects & Allocations">
          <div className="space-y-3">
            {delivery.project_allocations.map((proj, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2">
                  <Briefcase className="h-4 w-4 text-blue-500" />
                  <div>
                    <div className="font-semibold text-gray-900">{proj.name}</div>
                    <div className="text-xs text-gray-600">{proj.employees} employees allocated</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-gray-900">{proj.total_utilization}%</div>
                  <div className="text-xs text-gray-600">utilization</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Team Member Details */}
      <Card title="Team Members">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Name</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Title</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Current Project</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Billable Rate</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-700">Utilization</th>
              </tr>
            </thead>
            <tbody>
              {team.map((member) => (
                <tr key={member.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium text-gray-900">{member.name}</td>
                  <td className="py-3 px-4 text-gray-600">{member.title}</td>
                  <td className="py-3 px-4 text-center">
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                      member.current_project === "Bench"
                        ? "bg-orange-100 text-orange-800"
                        : "bg-green-100 text-green-800"
                    }`}>
                      {member.current_project}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center text-gray-900">${member.billable_rate}/hr</td>
                  <td className="py-3 px-4 text-center">
                    <div className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                      {member.utilization}%
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
