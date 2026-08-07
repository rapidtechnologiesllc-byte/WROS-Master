import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { TrendingUp, AlertCircle, Target } from "lucide-react";
import { Card, Button } from "../components/ui";
import { getPartnerROIKpis, getPartnerROITrend, getPartnerROIActions } from "../services/api/agents";
import { getCurrentUser } from "../services/api/users";

export default function PartnerROIAgentScreen() {
  const [partnerId, setPartnerId] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [trend, setTrend] = useState([]);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7));

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Get current user's Partner ID from auth context
        const user = await getCurrentUser();
        if (user?.id) {
          setPartnerId(user.id);

          // Fetch KPIs for selected month
          const kpis = await getPartnerROIKpis(user.id, selectedMonth);
          if (kpis) {
            setKpis(kpis);
          }

          // Fetch trend
          const trend = await getPartnerROITrend(user.id, 6);
          if (trend) {
            setTrend(trend);
          }

          // Fetch actions
          const actions = await getPartnerROIActions(user.id);
          if (actions) {
            setActions(actions);
          }
        }
      } catch (err) {
        toast.error("Failed to load Partner ROI dashboard");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedMonth]);

  if (loading) return <div className="p-6 text-center text-gray-500">Loading Partner ROI dashboard...</div>;
  if (!kpis) return <div className="p-6 text-center text-gray-500">No data available</div>;

  const statusBadge = (pct) => (
    <span className={`inline-block px-2 py-1 text-xs font-semibold rounded ${
      pct >= 70 ? "bg-green-100 text-green-700" : pct >= 50 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
    }`}>
      {pct.toFixed(0)}%
    </span>
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{kpis.partner_name} — ROI Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Real-time KPI tracking for your business unit</p>
        </div>
        <input
          type="month"
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
        />
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Revenue */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Revenue</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">${(kpis.revenue_usd / 1000000).toFixed(2)}M</div>
            </div>
            <TrendingUp className="h-6 w-6 text-blue-500" />
          </div>
        </Card>

        {/* Gross Margin */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Gross Margin</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{kpis.gross_margin_pct.toFixed(1)}%</div>
            </div>
            {statusBadge(kpis.gross_margin_pct)}
          </div>
        </Card>

        {/* Utilization */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">Utilization</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{kpis.practice_utilization_pct.toFixed(1)}%</div>
            </div>
            {statusBadge(kpis.practice_utilization_pct)}
          </div>
        </Card>

        {/* New Logos */}
        <Card>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase">New Logos</div>
              <div className="text-2xl font-bold text-gray-900 mt-2">{kpis.net_new_logos}</div>
            </div>
            <Target className="h-6 w-6 text-green-500" />
          </div>
        </Card>
      </div>

      {/* Actions Section */}
      {actions.length > 0 && (
        <Card title="Recommended Actions" className="mb-6">
          <div className="space-y-3">
            {actions.map((action, i) => (
              <div key={i} className={`flex gap-3 p-3 rounded-lg ${
                action.priority === "HIGH" ? "bg-red-50 border border-red-200" : "bg-amber-50 border border-amber-200"
              }`}>
                <AlertCircle className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
                  action.priority === "HIGH" ? "text-red-600" : "text-amber-600"
                }`} />
                <div className="flex-1">
                  <div className="font-semibold text-gray-900">{action.message}</div>
                  <div className="text-xs text-gray-600 mt-1">{action.category}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Trend Chart (simplified text-based) */}
      {trend.length > 0 && (
        <Card title="6-Month Trend">
          <div className="space-y-4">
            {trend.map((month) => (
              <div key={month.period} className="grid grid-cols-4 gap-4 pb-4 border-b last:border-0">
                <div>
                  <div className="text-xs text-gray-500">Period</div>
                  <div className="font-semibold text-gray-900">{month.period}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Revenue</div>
                  <div className="font-semibold text-gray-900">${(month.revenue_usd / 1000000).toFixed(2)}M</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Margin</div>
                  <div className="font-semibold text-gray-900">{month.gross_margin_pct.toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Utilization</div>
                  <div className="font-semibold text-gray-900">{month.practice_utilization_pct.toFixed(1)}%</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
