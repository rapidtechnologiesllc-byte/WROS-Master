import { useEffect, useState } from "react";
import { Users, TrendingUp, DollarSign, AlertCircle, Briefcase } from "lucide-react";
import { Card } from "../components/ui";
import { apiRequest } from "../services/api/client";
import DashboardBUPicker from "../components/DashboardBUPicker";

export default function BUHeadDashboardScreen() {
  const [dashboard, setDashboard] = useState(null);
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // A BU Head sees the BU they run; a partner / admin can switch between BUs
  const [buChoices, setBuChoices] = useState(null);
  const [selectedBuId, setSelectedBuId] = useState(null);
  const [targets, setTargets] = useState([]);

  useEffect(() => {
    fetchDashboardData(selectedBuId);
  }, [selectedBuId]);

  const fetchDashboardData = async (buId) => {
    setLoading(true);
    setError("");
    try {
      const qs = buId ? `?business_unit_id=${buId}` : "";
      const [dashRes, teamRes] = await Promise.all([
        apiRequest(`/dashboards/bu-head/summary${qs}`, { method: "GET" }),
        apiRequest(`/dashboards/bu-head/team${qs}`, { method: "GET" })
      ]);

      if (dashRes.data?.status === "needs_business_unit") {
        setBuChoices(dashRes.data.business_units || []);
        setDashboard(null);
        setTeam([]);
        return;
      }
      setDashboard(dashRes.data?.data);
      setTargets(dashRes.data?.targets_by_company || []);
      const allowed = dashRes.data?.business_units || [];
      setBuChoices(allowed.length > 1 ? allowed : null);
      if (!buId && dashRes.data?.business_unit_id) setSelectedBuId(dashRes.data.business_unit_id);
      setTeam(teamRes.data?.data?.team_members || []);
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
      console.error("[BUHeadDashboard] Failed to load:", err);
    } finally {
      setLoading(false);
    }
  };

  const picker = buChoices ? (
    <DashboardBUPicker businessUnits={buChoices} value={selectedBuId} onChange={setSelectedBuId} />
  ) : null;

  if (loading) return <div className="p-6 text-center text-gray-500">Loading BU dashboard...</div>;
  if (error) return <div className="p-6 space-y-4">{picker}<div className="text-center text-red-600">Error: {error}</div></div>;
  if (!dashboard) return <div className="p-6 space-y-4 max-w-7xl mx-auto">{picker || <div className="text-center text-gray-500">No data available</div>}</div>;

  const { team_size, revenue, delivery } = dashboard;
  const formatCurrency = (value) => `$${(value / 1000).toFixed(1)}k`;

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">{dashboard.bu_name} - Business Unit Dashboard</h1>
        <p className="text-gray-600 mt-1">Complete visibility of delivery, team, and revenue</p>
      </div>
      {picker}

      {targets.length > 0 && (
        <Card title="FY targets vs actuals by company">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-gray-500">
                  <th className="py-2 px-3">Company</th>
                  <th className="py-2 px-3">Revenue</th>
                  <th className="py-2 px-3">Billable headcount</th>
                  <th className="py-2 px-3">New logos</th>
                </tr>
              </thead>
              <tbody>
                {targets.map((t) => (
                  <tr key={t.company_id} className="border-b">
                    <td className="py-2 px-3 font-semibold">{t.company}</td>
                    {[["revenue", true], ["headcount", false], ["new_logos", false]].map(([key, usd]) => {
                      const cell = t.metrics[key] || {};
                      const show = (v) => (usd ? `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : Number(v || 0).toLocaleString());
                      return (
                        <td key={key} className="py-2 px-3">
                          {show(cell.actual)}{" "}
                          <span className="text-xs text-gray-500">/ {cell.target ? show(cell.target) : "no target"}</span>
                          {cell.progress_pct !== undefined && cell.progress_pct !== null && (
                            <span className="ml-1 text-xs text-gray-600">({cell.progress_pct}%)</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

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
