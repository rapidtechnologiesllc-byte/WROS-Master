import { apiFetch } from "../services/api/client";
import React, { useState, useEffect } from 'react';
import { TrendingUp, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

const SLMDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch SLM metrics
      const metricsRes = await apiFetch(`/api/v1/slm/metrics?time_range=${timeRange}`);
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      // Fetch recent SLM decisions
      const decisionsRes = await apiFetch(`/api/v1/slm/decisions?limit=50&time_range=${timeRange}`);
      if (decisionsRes.ok) {
        const decisionsData = await decisionsRes.json();
        setDecisions(decisionsData.decisions || []);
      }

      setError(null);
    } catch (err) {
      console.error('Failed to fetch SLM data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [timeRange]);

  const getRiskColor = (riskLevel) => {
    switch (riskLevel) {
      case 'LOW': return 'bg-green-100 text-green-800';
      case 'MEDIUM': return 'bg-yellow-100 text-yellow-800';
      case 'HIGH': return 'bg-orange-100 text-orange-800';
      case 'CRITICAL': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.85) return 'bg-green-100 text-green-800';
    if (confidence >= 0.7) return 'bg-yellow-100 text-yellow-800';
    if (confidence >= 0.5) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">SLM Decision Analytics</h1>
              <p className="text-gray-600">Specialized Language Model decision tracking, confidence analysis, and business impact</p>
            </div>

            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg bg-white"
            >
              <option value="1h">Last 1 Hour</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>
        </div>

        {/* Key Metrics */}
        {metrics && (
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg border p-6">
              <div className="text-gray-500 text-sm font-medium mb-2">Total Decisions</div>
              <div className="text-4xl font-bold text-gray-900">{metrics.last_24h?.total_decisions || 0}</div>
              <div className="text-sm text-gray-600 mt-2">in {timeRange}</div>
            </div>

            <div className="bg-white rounded-lg border p-6">
              <div className="text-gray-500 text-sm font-medium mb-2">Escalation Rate</div>
              <div className="text-4xl font-bold text-red-600">
                {((metrics.last_24h?.escalation_rate || 0) * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600 mt-2">
                {metrics.last_24h?.escalations || 0} escalated
              </div>
            </div>

            <div className="bg-white rounded-lg border p-6">
              <div className="text-gray-500 text-sm font-medium mb-2">Avg Confidence</div>
              <div className="text-4xl font-bold text-blue-600">
                {((metrics.last_24h?.avg_confidence || 0) * 100).toFixed(0)}%
              </div>
              <div className="text-sm text-gray-600 mt-2">Decision confidence</div>
            </div>

            <div className="bg-white rounded-lg border p-6">
              <div className="text-gray-500 text-sm font-medium mb-2">Business Impact</div>
              <div className="text-2xl font-bold text-green-600">
                ${(metrics.business_impact?.total_cost || 0) / 1000000}M
              </div>
              <div className="text-sm text-gray-600 mt-2">Cost impact tracked</div>
            </div>
          </div>
        )}

        {/* Message Type Breakdown */}
        {metrics?.by_message_type && (
          <div className="bg-white rounded-lg border p-6 mb-8">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Decisions by Message Type</h2>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(metrics.by_message_type).map(([msgType, data]) => (
                <div key={msgType} className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900 mb-3">{msgType}</div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Decisions:</span>
                      <span className="font-medium">{data.decisions}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Escalations:</span>
                      <span className="font-medium text-red-600">{data.escalations}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Rate:</span>
                      <span className="font-medium">
                        {data.decisions > 0
                          ? ((data.escalations / data.decisions) * 100).toFixed(1)
                          : 0}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Decisions */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="border-b px-6 py-4">
            <h2 className="text-xl font-bold text-gray-900">Recent SLM Decisions</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Message Type</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Confidence</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Risk Level</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Reasoning</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  <tr>
                    <td colSpan="6" className="px-6 py-4 text-center text-gray-500">Loading...</td>
                  </tr>
                ) : decisions.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-6 py-4 text-center text-gray-500">No decisions found</td>
                  </tr>
                ) : (
                  decisions.map((decision) => (
                    <tr key={decision.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{decision.message_type}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getConfidenceColor(decision.slm_confidence)}`}>
                          {(decision.slm_confidence * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getRiskColor(decision.risk_level)}`}>
                          {decision.risk_level}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {decision.was_escalated ? (
                          <div className="flex items-center gap-1 text-red-600">
                            <AlertTriangle className="w-4 h-4" />
                            Escalated
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 text-green-600">
                            <CheckCircle className="w-4 h-4" />
                            Proceed
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        <details className="cursor-pointer">
                          <summary className="text-blue-600 hover:text-blue-800">View</summary>
                          <div className="mt-2 bg-gray-100 p-2 rounded text-xs">
                            {decision.reasoning || 'No reasoning provided'}
                          </div>
                        </details>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {decision.analysis_at ? new Date(decision.analysis_at).toLocaleString() : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            Error: {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default SLMDashboard;
