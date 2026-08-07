import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { AlertTriangle, DollarSign, TrendingDown, Clock } from "lucide-react";
import { Card, Button } from "../components/ui";
import {
  getCFOFinancialSnapshot,
  getCFOAlerts,
  getCFOBUComparison,
  getCFOForecast
} from "../services/api/agents";

export default function CFOAgentScreen() {
  const [snapshot, setSnapshot] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [buComparison, setBuComparison] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Fetch financial snapshot
        const snapshot = await getCFOFinancialSnapshot();
        if (snapshot) {
          setSnapshot(snapshot);
        }

        // Fetch alerts
        const alerts = await getCFOAlerts();
        if (alerts) {
          setAlerts(alerts);
        }

        // Fetch BU comparison
        const buComparison = await getCFOBUComparison();
        if (buComparison) {
          setBuComparison(buComparison);
        }

        // Fetch forecast
        const forecast = await getCFOForecast();
        if (forecast) {
          setForecast(forecast);
        }
      } catch (err) {
        toast.error("Failed to load CFO dashboard");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div className="p-6 text-center text-gray-500">Loading CFO dashboard...</div>;
  if (!snapshot) return <div className="p-6 text-center text-gray-500">No data available</div>;

  const alertSeverityColor = (severity) => {
    const colors = {
      CRITICAL: "border-red-200 bg-red-50",
      HIGH: "border-amber-200 bg-amber-50",
      MEDIUM: "border-yellow-200 bg-yellow-50"
    };
    return colors[severity] || "border-gray-200 bg-gray-50";
  };

  const alertSeverityIcon = (severity) => {
    const colors = {
      CRITICAL: "text-red-600",
      HIGH: "text-amber-600",
      MEDIUM: "text-yellow-600"
    };
    return colors[severity] || "text-gray-600";
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">CFO Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Org-wide financial intelligence and alerts</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b">
        {["overview", "alerts", "bu-comparison", "forecast"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
              activeTab === tab
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-600 hover:text-gray-900"
            }`}
          >
            {tab === "overview" && "Overview"}
            {tab === "alerts" && "Alerts"}
            {tab === "bu-comparison" && "BU Comparison"}
            {tab === "forecast" && "Forecast"}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Card className="bg-gradient-to-br from-blue-50 to-blue-100/50">
              <div>
                <div className="text-xs font-semibold text-blue-600 uppercase">Revenue</div>
                <div className="text-2xl font-bold text-blue-900 mt-2">
                  ${(snapshot.total_revenue_usd / 1000000).toFixed(2)}M
                </div>
                <div className="text-xs text-blue-600 mt-1">{snapshot.period}</div>
              </div>
            </Card>

            <Card className="bg-gradient-to-br from-green-50 to-green-100/50">
              <div>
                <div className="text-xs font-semibold text-green-600 uppercase">Gross Margin</div>
                <div className="text-2xl font-bold text-green-900 mt-2">{snapshot.gross_margin_pct.toFixed(1)}%</div>
                <div className="text-xs text-green-600 mt-1">Target: 20%</div>
              </div>
            </Card>

            <Card className="bg-gradient-to-br from-purple-50 to-purple-100/50">
              <div>
                <div className="text-xs font-semibold text-purple-600 uppercase">Cash Position</div>
                <div className="text-2xl font-bold text-purple-900 mt-2">
                  ${(snapshot.cash_position_usd / 1000000).toFixed(1)}M
                </div>
                <div className="text-xs text-purple-600 mt-1">Paid invoices</div>
              </div>
            </Card>

            <Card className="bg-gradient-to-br from-orange-50 to-orange-100/50">
              <div>
                <div className="text-xs font-semibold text-orange-600 uppercase">Open Disputes</div>
                <div className="text-2xl font-bold text-orange-900 mt-2">{snapshot.open_disputes_count}</div>
                <div className="text-xs text-orange-600 mt-1">Pending resolution</div>
              </div>
            </Card>
          </div>

          {/* Key Metrics */}
          <Card title="Key Financial Metrics">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <div className="text-xs text-gray-500 uppercase">Net Position</div>
                <div className="text-xl font-bold text-gray-900 mt-1">
                  ${(snapshot.net_position_usd / 1000000).toFixed(2)}M
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 uppercase">Cost of Delivery</div>
                <div className="text-xl font-bold text-gray-900 mt-1">
                  ${(snapshot.cost_of_delivery_usd / 1000000).toFixed(2)}M
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 uppercase">Revenue Leakage</div>
                <div className="text-xl font-bold text-amber-600 mt-1">{snapshot.revenue_leakage_hours.toFixed(0)} hrs</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 uppercase">Reserve Fund</div>
                <div className="text-xl font-bold text-gray-900 mt-1">
                  ${(snapshot.reserve_fund_current_usd / 1000000).toFixed(1)}M / ${(snapshot.reserve_fund_target_usd / 1000000).toFixed(1)}M
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <div>
          {alerts.length === 0 ? (
            <Card>
              <div className="text-center text-gray-500 py-8">No critical alerts</div>
            </Card>
          ) : (
            <div className="space-y-4">
              {alerts.map((alert, i) => (
                <Card key={i} className={`border ${alertSeverityColor(alert.severity)}`}>
                  <div className="flex gap-4">
                    <AlertTriangle className={`h-6 w-6 flex-shrink-0 mt-1 ${alertSeverityIcon(alert.severity)}`} />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-semibold text-gray-900">{alert.type}</h3>
                        <span className={`text-xs font-semibold px-2 py-1 rounded ${
                          alert.severity === "CRITICAL" ? "bg-red-200 text-red-700" : "bg-amber-200 text-amber-700"
                        }`}>
                          {alert.severity}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700">{alert.message}</p>
                      <p className="text-xs text-gray-600 mt-2">→ {alert.recommendation}</p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* BU Comparison Tab */}
      {activeTab === "bu-comparison" && (
        <div>
          {buComparison.length === 0 ? (
            <Card>
              <div className="text-center text-gray-500 py-8">No BU data available</div>
            </Card>
          ) : (
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b">
                    <tr>
                      <th className="text-left py-3 px-4 font-semibold text-gray-900">Partner / BU</th>
                      <th className="text-right py-3 px-4 font-semibold text-gray-900">Revenue</th>
                      <th className="text-right py-3 px-4 font-semibold text-gray-900">Cost</th>
                      <th className="text-right py-3 px-4 font-semibold text-gray-900">Net Position</th>
                      <th className="text-right py-3 px-4 font-semibold text-gray-900">Margin %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {buComparison.map((bu, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-3 px-4">{bu.partner_name}</td>
                        <td className="text-right py-3 px-4">${(bu.revenue_usd / 1000000).toFixed(2)}M</td>
                        <td className="text-right py-3 px-4">${(bu.cost_usd / 1000000).toFixed(2)}M</td>
                        <td className="text-right py-3 px-4 font-semibold">${(bu.net_position_usd / 1000000).toFixed(2)}M</td>
                        <td className="text-right py-3 px-4 font-semibold">
                          <span className={bu.margin_pct >= 15 ? "text-green-600" : "text-red-600"}>
                            {bu.margin_pct.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Forecast Tab */}
      {activeTab === "forecast" && forecast && (
        <div>
          <Card>
            <div className="mb-4 text-sm text-gray-600">{forecast.forecast_basis}</div>
            <div className="space-y-3">
              {forecast.months.map((month, i) => (
                <div key={i} className="flex items-center justify-between pb-3 border-b last:border-0">
                  <div>
                    <div className="font-semibold text-gray-900">{month.month}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-gray-900">${(month.forecast_revenue_usd / 1000000).toFixed(2)}M</div>
                    <div className="text-xs text-gray-500">Forecast</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
