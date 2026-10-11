import { apiFetch } from "../services/api/client";
import React, { useState, useEffect } from 'react';
import { AlertCircle, TrendingUp, Zap, Database, RefreshCw, CheckCircle, ChevronDown, ChevronUp, Filter } from 'lucide-react';

export default function SLMLearningTranscript() {
  const [transcripts, setTranscripts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [modulePerformance, setModulePerformance] = useState(null);
  const [cascadeChain, setCascadeChain] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  // Filter state
  const [filters, setFilters] = useState({
    module: '',
    decisionType: '',
    startDate: '',
    endDate: '',
    limit: 50,
    offset: 0
  });

  const [selectedTranscript, setSelectedTranscript] = useState(null);
  const [showDetailView, setShowDetailView] = useState(false);

  useEffect(() => {
    loadLearningData();
    // Refresh every 5 minutes
    const interval = setInterval(loadLearningData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [filters]);

  const loadLearningData = async () => {
    try {
      setLoading(true);

      // Build query string
      const params = new URLSearchParams();
      if (filters.module) params.append('module_name', filters.module);
      if (filters.decisionType) params.append('decision_type', filters.decisionType);
      if (filters.startDate) params.append('start_date', filters.startDate);
      if (filters.endDate) params.append('end_date', filters.endDate);
      params.append('limit', filters.limit);
      params.append('offset', filters.offset);

      // Load transcript list
      const transcriptResp = await apiFetch(`/api/v1/learning/transcript/all?${params}`);
      if (transcriptResp.ok) {
        const data = await transcriptResp.json();
        setTranscripts(data.data || []);
      }

      // Load audit summary
      const summaryResp = await apiFetch('/api/v1/learning/audit-summary?period=daily&days=30');
      if (summaryResp.ok) {
        const data = await summaryResp.json();
        setSummary(data);
      }

      // Load module performance
      const perfResp = await apiFetch('/api/v1/learning/module-performance?days=30');
      if (perfResp.ok) {
        const data = await perfResp.json();
        setModulePerformance(data.modules || {});
      }
    } catch (error) {
      console.error('Failed to load learning data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTranscriptDetail = async (transcriptId) => {
    try {
      const resp = await apiFetch(`/api/v1/learning/transcript/${transcriptId}`);
      if (resp.ok) {
        const data = await resp.json();
        setSelectedTranscript(data.transcript);
        if (data.cascade_chain) {
          setCascadeChain(data.cascade_chain);
        }
        setShowDetailView(true);
      }
    } catch (error) {
      console.error('Failed to load transcript detail:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, offset: 0 }));
  };

  if (loading && transcripts.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-4" size={32} />
          <p>Loading Learning Transcripts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-indigo-700 text-white p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Database size={32} /> Learning Transcript Audit
            </h1>
            <p className="text-indigo-100 mt-2">Complete decision audit log with confidence gaps, weight updates, and cascade impacts</p>
          </div>
          <button
            onClick={loadLearningData}
            className="bg-white bg-opacity-20 hover:bg-opacity-30 px-4 py-2 rounded flex items-center gap-2"
          >
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* Filter Section */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <div className="flex items-center gap-2 mb-4">
          <Filter size={20} />
          <h2 className="text-lg font-semibold">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Module</label>
            <select
              value={filters.module}
              onChange={(e) => handleFilterChange('module', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">All Modules</option>
              <option value="sales">Sales</option>
              <option value="thunder">Thunder</option>
              <option value="recruitment">Recruitment</option>
              <option value="flash">Flash</option>
              <option value="finance">Finance</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Decision Type</label>
            <input
              type="text"
              value={filters.decisionType}
              onChange={(e) => handleFilterChange('decisionType', e.target.value)}
              placeholder="e.g. predict_fit"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <input
              type="date"
              value={filters.startDate}
              onChange={(e) => handleFilterChange('startDate', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <input
              type="date"
              value={filters.endDate}
              onChange={(e) => handleFilterChange('endDate', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Limit</label>
            <input
              type="number"
              value={filters.limit}
              onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
              min="1"
              max="1000"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      {summary && summary.data && summary.data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Accuracy Rate</p>
                <p className="text-2xl font-bold text-blue-600">{(summary.data[0]?.accuracy_rate || 0).toFixed(1)}%</p>
              </div>
              <CheckCircle size={24} className="text-blue-600" />
            </div>
          </div>
          <div className="bg-green-50 p-4 rounded-lg border border-green-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Avg Confidence Gap</p>
                <p className="text-2xl font-bold text-green-600">{(summary.data[0]?.avg_confidence_gap || 0).toFixed(3)}</p>
              </div>
              <TrendingUp size={24} className="text-green-600" />
            </div>
          </div>
          <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Learning Strength</p>
                <p className="text-2xl font-bold text-purple-600">{(summary.data[0]?.avg_learning_strength || 0).toFixed(3)}</p>
              </div>
              <Zap size={24} className="text-purple-600" />
            </div>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Cascade Success Rate</p>
                <p className="text-2xl font-bold text-orange-600">{(summary.data[0]?.cascade_success_rate || 0).toFixed(1)}%</p>
              </div>
              <CheckCircle size={24} className="text-orange-600" />
            </div>
          </div>
        </div>
      )}

      {/* Module Performance */}
      {modulePerformance && (
        <div className="bg-white p-6 rounded-lg border border-gray-200">
          <h2 className="text-xl font-semibold mb-4">Module Performance Comparison</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold">Module</th>
                  <th className="px-4 py-2 text-right font-semibold">Total Decisions</th>
                  <th className="px-4 py-2 text-right font-semibold">Accuracy Rate</th>
                  <th className="px-4 py-2 text-right font-semibold">Avg Gap</th>
                  <th className="px-4 py-2 text-right font-semibold">Learning Strength</th>
                  <th className="px-4 py-2 text-right font-semibold">Cascade Impacts</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {Object.entries(modulePerformance).map(([module, stats]) => (
                  <tr key={module} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium capitalize">{module}</td>
                    <td className="px-4 py-2 text-right">{stats.total_decisions || 0}</td>
                    <td className="px-4 py-2 text-right">
                      <span className={stats.accuracy_rate > 80 ? 'text-green-600 font-semibold' : 'text-orange-600'}>
                        {(stats.accuracy_rate || 0).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">{(stats.avg_gap || 0).toFixed(3)}</td>
                    <td className="px-4 py-2 text-right">{(stats.avg_learning_strength || 0).toFixed(3)}</td>
                    <td className="px-4 py-2 text-right">{stats.cascade_impacts || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Transcript List */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h2 className="text-xl font-semibold mb-4">Learning Transcript Entries ({transcripts.length})</h2>
        <div className="space-y-2">
          {transcripts.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No learning transcripts found</p>
          ) : (
            transcripts.map((transcript) => (
              <div key={transcript.id} className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  onClick={() => {
                    if (expandedId === transcript.id) {
                      setExpandedId(null);
                    } else {
                      setExpandedId(transcript.id);
                      loadTranscriptDetail(transcript.id);
                    }
                  }}
                  className="w-full text-left p-4 hover:bg-gray-50 flex items-center justify-between"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{transcript.module_name}</span>
                      <span className="text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded">{transcript.decision_type}</span>
                      {transcript.confidence_gap !== null && (
                        <span className={`text-sm font-mono ${Math.abs(transcript.confidence_gap) < 0.1 ? 'text-green-600' : 'text-orange-600'}`}>
                          Gap: {Math.abs(transcript.confidence_gap).toFixed(3)}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-600 mt-1">
                      Predicted: {transcript.predicted_label || transcript.predicted_value?.toFixed(3)}
                      {transcript.actual_label && ` → Actual: ${transcript.actual_label || transcript.actual_value?.toFixed(3)}`}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{new Date(transcript.created_at).toLocaleString()}</div>
                  </div>
                  {expandedId === transcript.id ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {expandedId === transcript.id && (
                  <div className="bg-gray-50 p-4 border-t border-gray-200 space-y-4">
                    {selectedTranscript && selectedTranscript.id === transcript.id && (
                      <>
                        <div>
                          <h4 className="font-semibold text-sm mb-2">Decision Factors</h4>
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                            {selectedTranscript.factors && Object.entries(selectedTranscript.factors).map(([factor, weight]) => (
                              <div key={factor} className="bg-white p-2 rounded border border-gray-200">
                                <div className="font-medium">{factor}</div>
                                <div className="text-gray-600">Weight: {(weight).toFixed(3)}</div>
                                {selectedTranscript.factor_values?.[factor] && (
                                  <div className="text-gray-500">Value: {selectedTranscript.factor_values[factor]}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>

                        {selectedTranscript.weights_before && selectedTranscript.weights_after && (
                          <div>
                            <h4 className="font-semibold text-sm mb-2">Weight Updates</h4>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                              {Object.entries(selectedTranscript.weights_before).map(([factor, before]) => {
                                const after = selectedTranscript.weights_after?.[factor] || before;
                                const delta = after - before;
                                return (
                                  <div key={factor} className="bg-white p-2 rounded border border-gray-200">
                                    <div className="font-medium">{factor}</div>
                                    <div className="text-xs text-gray-600">
                                      {before.toFixed(3)} → {after.toFixed(3)}
                                    </div>
                                    {delta !== 0 && (
                                      <div className={`text-xs font-mono ${delta > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {delta > 0 ? '+' : ''}{delta.toFixed(3)}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {cascadeChain && (
                          <div>
                            <h4 className="font-semibold text-sm mb-2">Cascade Chain ({cascadeChain.chain_type})</h4>
                            <div className="bg-white p-3 rounded border border-gray-200 text-sm">
                              <div className="flex items-center gap-2 flex-wrap">
                                {cascadeChain.steps?.map((step, idx) => (
                                  <React.Fragment key={step.step_number}>
                                    <div className="bg-blue-50 px-3 py-1 rounded text-xs">
                                      <div className="font-medium">{step.step_name}</div>
                                      <div className="text-gray-600">{step.predicted} → {step.actual}</div>
                                      <div className="text-gray-500">Gap: {step.gap?.toFixed(3)}</div>
                                    </div>
                                    {idx < cascadeChain.steps.length - 1 && <span className="text-gray-400">→</span>}
                                  </React.Fragment>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}

                        {selectedTranscript.cascade_impacts && Object.keys(selectedTranscript.cascade_impacts).length > 0 && (
                          <div>
                            <h4 className="font-semibold text-sm mb-2">Cascade Impacts</h4>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                              {Object.entries(selectedTranscript.cascade_impacts).map(([module, effect]) => (
                                <div key={module} className="bg-white p-2 rounded border border-gray-200">
                                  <div className="font-medium capitalize">{module}</div>
                                  <div className="text-gray-600">{effect}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="text-xs text-gray-500 bg-white p-2 rounded border border-gray-200">
                          <div>Learning Strength: {selectedTranscript.learning_strength?.toFixed(3)}</div>
                          <div>Source: {selectedTranscript.source}</div>
                          {selectedTranscript.manual_override && (
                            <div className="text-orange-600">Manually Overridden: {selectedTranscript.override_reason}</div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
