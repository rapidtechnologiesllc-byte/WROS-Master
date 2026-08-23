import React, { useState, useEffect } from 'react';
import { AlertCircle, TrendingUp, Zap, Database, RefreshCw, CheckCircle } from 'lucide-react';

export default function SLMDashboard() {
  const [stats, setStats] = useState(null);
  const [report, setReport] = useState(null);
  const [trajectory, setTrajectory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedField, setSelectedField] = useState(null);

  useEffect(() => {
    loadDashboardData();
    // Refresh every 5 minutes
    const interval = setInterval(loadDashboardData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);

      // Load stats
      const statsResp = await fetch('/api/v1/slm/feedback/stats?days=7');
      if (statsResp.ok) {
        setStats(await statsResp.json());
      }

      // Load report
      const reportResp = await fetch('/api/v1/slm/feedback/report');
      if (reportResp.ok) {
        const reportData = await reportResp.json();
        setReport(reportData.report_structured);
      }

      // Load trajectory
      const trajResp = await fetch('/api/v1/slm/feedback/trajectory');
      if (trajResp.ok) {
        setTrajectory(await trajResp.json());
      }
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4" size={32} />
          <p>Loading SLM Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Zap size={32} /> Resume Parser (SLM)
            </h1>
            <p className="text-blue-100 mt-2">Self-Learning Model - Real-time accuracy monitoring</p>
          </div>
          <button
            onClick={loadDashboardData}
            className="bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded flex items-center gap-2"
          >
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* Performance Overview */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-gray-500 text-sm font-semibold">TOTAL FEEDBACK</div>
            <div className="text-3xl font-bold">{stats.total_feedback}</div>
            <div className="text-xs text-gray-400 mt-1">Last 7 days</div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-gray-500 text-sm font-semibold">CORRECTIONS</div>
            <div className="text-3xl font-bold text-red-600">{stats.corrections}</div>
            <div className="text-xs text-gray-400 mt-1">{stats.correction_rate}% error rate</div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-gray-500 text-sm font-semibold">VALIDATIONS</div>
            <div className="text-3xl font-bold text-green-600">{stats.validations}</div>
            <div className="text-xs text-gray-400 mt-1">Correct extractions</div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-gray-500 text-sm font-semibold">READY TO RETRAIN</div>
            <div className={`text-3xl font-bold ${stats.ready_to_retrain ? 'text-green-600' : 'text-yellow-600'}`}>
              {stats.ready_to_retrain ? '✓' : '○'}
            </div>
            <div className="text-xs text-gray-400 mt-1">{stats.ready_to_retrain ? 'Yes' : 'Accumulating'}</div>
          </div>
        </div>
      )}

      {/* Accuracy by Field */}
      {stats?.by_field && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <TrendingUp size={20} /> Accuracy by Field
          </h2>

          <div className="grid grid-cols-3 gap-4">
            {Object.entries(stats.by_field).map(([field, data]) => {
              const accuracy = data.accuracy_implied || 0;
              const isLow = accuracy < 75;

              return (
                <div
                  key={field}
                  className={`p-4 rounded-lg cursor-pointer border-2 transition ${
                    selectedField === field ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
                  }`}
                  onClick={() => setSelectedField(selectedField === field ? null : field)}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="font-semibold capitalize">{field}</div>
                    <div className={`text-2xl font-bold ${isLow ? 'text-red-600' : 'text-green-600'}`}>
                      {accuracy.toFixed(1)}%
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                    <div
                      className={`h-2 rounded-full transition ${
                        isLow ? 'bg-red-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${accuracy}%` }}
                    />
                  </div>

                  <div className="text-xs text-gray-500">
                    {data.total_feedback} feedback items
                  </div>

                  {isLow && (
                    <div className="text-xs text-red-600 mt-2 flex items-center gap-1">
                      <AlertCircle size={12} /> Needs improvement
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Daily Report */}
      {report && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Today's Improvement Report</h2>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-700 mb-3">Collected Today</h3>
              <div className="space-y-2">
                <div>Feedback: <span className="font-bold">{report.feedback_collected}</span></div>
                <div>Errors fixed: <span className="font-bold">{report.errors_fixed}</span></div>
                <div>Fields improved: <span className="font-bold">{report.fields_improved.length}</span></div>
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-700 mb-3">Status</h3>
              <div className={`p-3 rounded ${report.ready_to_deploy ? 'bg-green-50' : 'bg-yellow-50'}`}>
                <div className="flex items-center gap-2 mb-2">
                  {report.ready_to_deploy ? (
                    <>
                      <CheckCircle className="text-green-600" size={20} />
                      <span className="font-semibold text-green-700">Ready to Deploy</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="text-yellow-600" size={20} />
                      <span className="font-semibold text-yellow-700">Learning</span>
                    </>
                  )}
                </div>
                <p className="text-sm text-gray-600">{report.retrain_reason}</p>
              </div>
            </div>
          </div>

          <div className="mt-4 p-3 bg-blue-50 border-l-4 border-blue-500 rounded">
            <p className="text-sm text-blue-700">
              <strong>Next Action:</strong> {report.next_action}
            </p>
          </div>
        </div>
      )}

      {/* Accuracy Trajectory */}
      {trajectory && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <TrendingUp size={20} /> 90-Day Accuracy Projection
          </h2>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="text-gray-500 text-sm mb-2">Current Estimate</div>
              <div className="text-4xl font-bold text-blue-600">
                {trajectory.current_estimate || trajectory.baseline_accuracy}%
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Baseline: {trajectory.baseline_accuracy}%
              </div>
            </div>

            <div>
              <div className="text-gray-500 text-sm mb-2">Projected in 3 Months</div>
              <div className="text-4xl font-bold text-green-600">
                {trajectory.projections?.[trajectory.projections.length - 1]?.projected_accuracy || '95%'}
              </div>
              <div className="text-xs text-gray-400 mt-1">Estimated improvement</div>
            </div>
          </div>

          {/* Chart */}
          <div className="mt-6 pt-4 border-t">
            <div className="text-sm font-semibold text-gray-700 mb-3">Milestone Timeline</div>
            <div className="space-y-2">
              {trajectory.projections?.slice(-4).map((proj) => (
                <div key={proj.day} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{proj.milestone}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-40 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${proj.projected_accuracy}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold min-w-12">{proj.projected_accuracy.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Recommendations */}
      {stats && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Recommendations</h2>

          <div className="space-y-3">
            {stats.low_confidence_fields.length > 0 && (
              <div className="p-4 bg-red-50 border border-red-200 rounded">
                <h3 className="font-semibold text-red-700 mb-2">Low Accuracy Fields</h3>
                <p className="text-sm text-red-600 mb-3">
                  These fields need improvement and should be prioritized:
                </p>
                <div className="space-y-1">
                  {stats.low_confidence_fields.map(([field, accuracy]) => (
                    <div key={field} className="text-sm text-red-600">
                      • <strong>{field}</strong>: {accuracy.toFixed(1)}% accuracy
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="p-4 bg-blue-50 border border-blue-200 rounded">
              <h3 className="font-semibold text-blue-700 mb-2">System Recommendation</h3>
              <p className="text-sm text-blue-600">{stats.recommendation}</p>
            </div>
          </div>
        </div>
      )}

      {/* Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Database size={20} /> Configuration
        </h2>

        <div className="grid grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-gray-700 mb-3">Current Model</h3>
            <div className="space-y-2 text-sm">
              <div>Model: <span className="font-mono bg-gray-100 px-2 py-1 rounded">resume_parser_slm v1.0</span></div>
              <div>Type: <span className="font-bold">Pattern-Based (SLM)</span></div>
              <div>Baseline Accuracy: <span className="font-bold">70%</span></div>
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-gray-700 mb-3">Next Generation</h3>
            <div className="space-y-2 text-sm">
              <div>Model: <span className="font-mono bg-blue-100 px-2 py-1 rounded">resume_parser_bert v1.0</span></div>
              <div>Type: <span className="font-bold">ML-Based (BERT)</span></div>
              <div>Target Accuracy: <span className="font-bold">92%+</span></div>
            </div>
          </div>
        </div>

        <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
          <p className="text-sm text-yellow-700">
            <strong>⚡ Ready to train BERT model?</strong> Run the training pipeline to achieve 92%+ accuracy with your real and synthetic training data.
          </p>
          <div className="mt-2 text-xs text-gray-600">
            See <code className="bg-gray-100 px-1 rounded">BERT_TRAINING_GUIDE.md</code> for step-by-step instructions.
          </div>
        </div>
      </div>
    </div>
  );
}
