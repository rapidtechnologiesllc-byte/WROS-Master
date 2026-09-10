import React, { useState, useEffect } from 'react';
import { RefreshCw, AlertCircle, CheckCircle, Clock, Zap } from 'lucide-react';

const MessageQueueMonitor = () => {
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState('');
  const [messageTypeFilter, setMessageTypeFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch messages
      const messagesRes = await fetch(
        `/api/v1/message-queue/display?status=${filter}&message_type=${messageTypeFilter}&limit=100`
      );
      const messagesData = await messagesRes.json();
      setMessages(messagesData.messages || []);

      // Fetch stats
      const statsRes = await fetch('/api/v1/message-queue/stats');
      const statsData = await statsRes.json();
      setStats(statsData);

      setError(null);
    } catch (err) {
      console.error('Failed to fetch queue data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    if (autoRefresh) {
      const interval = setInterval(fetchData, 3000); // Refresh every 3s
      return () => clearInterval(interval);
    }
  }, [filter, messageTypeFilter, autoRefresh]);

  const handleRetry = async (messageId) => {
    try {
      const res = await fetch(`/api/v1/message-queue/${messageId}/retry`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchData();
      }
    } catch (err) {
      console.error('Retry failed:', err);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'PENDING': return 'bg-yellow-100 text-yellow-800';
      case 'PROCESSING': return 'bg-blue-100 text-blue-800';
      case 'COMPLETED': return 'bg-green-100 text-green-800';
      case 'FAILED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'PENDING': return <Clock className="w-4 h-4" />;
      case 'PROCESSING': return <Zap className="w-4 h-4" />;
      case 'COMPLETED': return <CheckCircle className="w-4 h-4" />;
      case 'FAILED': return <AlertCircle className="w-4 h-4" />;
      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Message Queue Monitor</h1>
          <p className="text-gray-600">Real-time visibility into job creation, SLM analysis, and FLASH recruiter pipeline</p>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-5 gap-4 mb-8">
            <div className="bg-white rounded-lg border p-4">
              <div className="text-gray-500 text-sm">Total</div>
              <div className="text-3xl font-bold text-gray-900">{stats.total_messages}</div>
            </div>
            <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
              <div className="text-yellow-700 text-sm font-medium">Pending</div>
              <div className="text-3xl font-bold text-yellow-900">{stats.pending}</div>
            </div>
            <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
              <div className="text-blue-700 text-sm font-medium">Processing</div>
              <div className="text-3xl font-bold text-blue-900">{stats.processing}</div>
            </div>
            <div className="bg-green-50 rounded-lg border border-green-200 p-4">
              <div className="text-green-700 text-sm font-medium">Completed</div>
              <div className="text-3xl font-bold text-green-900">{stats.completed}</div>
            </div>
            <div className="bg-red-50 rounded-lg border border-red-200 p-4">
              <div className="text-red-700 text-sm font-medium">Failed</div>
              <div className="text-3xl font-bold text-red-900">{stats.failed}</div>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="bg-white rounded-lg border p-4 mb-8">
          <div className="flex items-center gap-4 mb-4">
            <button
              onClick={fetchData}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm text-gray-700">Auto-refresh (3s)</span>
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Status Filter</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">All Statuses</option>
                <option value="PENDING">Pending</option>
                <option value="PROCESSING">Processing</option>
                <option value="COMPLETED">Completed</option>
                <option value="FAILED">Failed</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Message Type Filter</label>
              <select
                value={messageTypeFilter}
                onChange={(e) => setMessageTypeFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">All Types</option>
                <option value="job_created_flash">Job Created (FLASH)</option>
                <option value="flash_recruiter">FLASH Recruiter</option>
                <option value="slm_training_alert">SLM Training Alert</option>
                <option value="cascade_failure_signal">Cascade Failure</option>
              </select>
            </div>
          </div>
        </div>

        {/* Messages Table */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Type</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Created</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Retries</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Result</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Error</th>
                  <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  <tr>
                    <td colSpan="7" className="px-6 py-4 text-center text-gray-500">Loading...</td>
                  </tr>
                ) : messages.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-6 py-4 text-center text-gray-500">No messages found</td>
                  </tr>
                ) : (
                  messages.map((msg) => (
                    <tr key={msg.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{msg.type}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(msg.status)}`}>
                          {getStatusIcon(msg.status)}
                          {msg.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {msg.created_at ? new Date(msg.created_at).toLocaleString() : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{msg.retry_count || 0}</td>
                      <td className="px-6 py-4 text-sm">
                        <details className="cursor-pointer">
                          <summary className="text-blue-600 hover:text-blue-800">View</summary>
                          <pre className="mt-2 bg-gray-100 p-2 rounded text-xs overflow-auto max-h-40">
                            {msg.result ? JSON.stringify(JSON.parse(msg.result), null, 2) : 'No result'}
                          </pre>
                        </details>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {msg.error ? (
                          <details className="cursor-pointer">
                            <summary className="text-red-600 hover:text-red-800">View</summary>
                            <div className="mt-2 bg-red-50 p-2 rounded text-xs overflow-auto max-h-40">
                              {msg.error}
                            </div>
                          </details>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {msg.status === 'FAILED' && (
                          <button
                            onClick={() => handleRetry(msg.id)}
                            className="text-blue-600 hover:text-blue-800 font-medium"
                          >
                            Retry
                          </button>
                        )}
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

export default MessageQueueMonitor;
