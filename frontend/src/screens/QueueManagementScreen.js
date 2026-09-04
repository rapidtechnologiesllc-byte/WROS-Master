import React, { useState, useEffect } from 'react';
import { ChevronDown, RefreshCw, Trash2, Eye, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { apiRequest } from '../services/api/client';

const QueueManagementScreen = () => {
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [limit] = useState(25);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [expandedStats, setExpandedStats] = useState(true);

  const QUEUE_TYPES = [
    'THUNDER_QUEUE',
    'EMAIL_QUEUE',
    'WHATSAPP_QUEUE',
    'SMS_QUEUE',
    'SLACK_QUEUE',
    'APPROVAL_QUEUE',
    'COMMISSION_QUEUE',
    'CRM_QUEUE',
    'DASHBOARD_QUEUE',
    'CALENDAR_QUEUE',
    'SIGNATURE_QUEUE'
  ];

  const STATUSES = ['PENDING', 'SLM_PROCESSING', 'CHANNEL_QUEUED', 'COMPLETED', 'FAILED'];

  // Fetch messages
  const fetchMessages = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        skip: currentPage * limit,
        limit: limit
      });
      if (selectedQueue) {
        params.append('queue_type', selectedQueue);
      }
      const response = await apiRequest(`/queues?${params.toString()}`);
      setMessages(response.data || []);
    } catch (err) {
      setError(err.message || 'Failed to load messages');
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await apiRequest('/queues/stats');
      setStats(response);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  // Initial load and polling
  useEffect(() => {
    fetchMessages();
    fetchStats();

    // Poll every 5 seconds
    const interval = setInterval(() => {
      fetchMessages();
      fetchStats();
    }, 5000);

    return () => clearInterval(interval);
  }, [selectedQueue, currentPage]);

  // Retry message
  const handleRetry = async (messageId) => {
    try {
      await apiRequest(`/queues/${messageId}/retry`, {
        method: 'POST'
      });
      fetchMessages();
      setError(null);
    } catch (err) {
      setError(`Failed to retry message: ${err.message}`);
    }
  };

  // Clear message
  const handleClear = async (messageId) => {
    try {
      await apiRequest(`/queues/${messageId}/clear`, {
        method: 'POST'
      });
      fetchMessages();
      setError(null);
    } catch (err) {
      setError(`Failed to clear message: ${err.message}`);
    }
  };

  // Get message details
  const handleViewDetails = async (messageId) => {
    try {
      const response = await apiRequest(`/queues/${messageId}`);
      setSelectedMessage(response);
    } catch (err) {
      setError(`Failed to load message details: ${err.message}`);
    }
  };

  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'PENDING':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'SLM_PROCESSING':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'CHANNEL_QUEUED':
        return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'COMPLETED':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'FAILED':
        return 'bg-red-100 text-red-800 border-red-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  // Get status icon
  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-4 h-4" />;
      case 'FAILED':
        return <AlertCircle className="w-4 h-4" />;
      case 'PENDING':
      case 'SLM_PROCESSING':
      case 'CHANNEL_QUEUED':
        return <Clock className="w-4 h-4" />;
      default:
        return null;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Message Queue Management</h1>
        <p className="text-gray-600">Monitor and manage system messages across all channels</p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Queue Statistics */}
      {stats && (
        <div className="mb-8 bg-white rounded-lg border border-gray-200 shadow-sm">
          <button
            onClick={() => setExpandedStats(!expandedStats)}
            className="w-full p-4 flex items-center justify-between hover:bg-gray-50"
          >
            <h2 className="text-lg font-semibold text-gray-900">Queue Statistics</h2>
            <ChevronDown className={`w-5 h-5 transition-transform ${expandedStats ? 'rotate-180' : ''}`} />
          </button>

          {expandedStats && (
            <div className="px-4 pb-4 border-t border-gray-200">
              {/* Email Metrics */}
              {stats.email_metrics && (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h3 className="font-semibold text-blue-900 mb-3">Email Engagement Metrics</h3>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div>
                      <div className="text-sm text-blue-700">Total Sent</div>
                      <div className="text-2xl font-bold text-blue-900">{stats.email_metrics.total_sent || 0}</div>
                    </div>
                    <div>
                      <div className="text-sm text-blue-700">Open Rate</div>
                      <div className="text-2xl font-bold text-blue-900">{stats.email_metrics.open_rate || 0}%</div>
                    </div>
                    <div>
                      <div className="text-sm text-blue-700">Click Rate</div>
                      <div className="text-2xl font-bold text-blue-900">{stats.email_metrics.click_rate || 0}%</div>
                    </div>
                    <div>
                      <div className="text-sm text-blue-700">Bounce Rate</div>
                      <div className="text-2xl font-bold text-blue-900">{stats.email_metrics.bounce_rate || 0}%</div>
                    </div>
                    <div>
                      <div className="text-sm text-blue-700">Reply Rate</div>
                      <div className="text-2xl font-bold text-blue-900">{stats.email_metrics.reply_rate || 0}%</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Queue Breakdown */}
              <h3 className="font-semibold text-gray-900 mb-3">Queue Status Breakdown</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {stats.queues && Object.entries(stats.queues).map(([queueType, queueStats]) => (
                  <div
                    key={queueType}
                    className="p-4 border border-gray-200 rounded-lg hover:shadow-md cursor-pointer transition-shadow"
                    onClick={() => {
                      setSelectedQueue(selectedQueue === queueType ? null : queueType);
                      setCurrentPage(0);
                    }}
                  >
                    <h4 className="font-semibold text-gray-900 mb-2">{queueType}</h4>
                    <div className="text-sm space-y-1">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total:</span>
                        <span className="font-medium">{queueStats.total || 0}</span>
                      </div>
                      {Object.entries(queueStats).map(([status, count]) => (
                        status !== 'total' && (
                          <div key={status} className="flex justify-between text-xs">
                            <span className="text-gray-500">{status}:</span>
                            <span className="text-gray-700">{count || 0}</span>
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Queue Filter */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">Filter by Queue Type</label>
          <select
            value={selectedQueue || ''}
            onChange={(e) => {
              setSelectedQueue(e.target.value || null);
              setCurrentPage(0);
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">All Queues</option>
            {QUEUE_TYPES.map(queueType => (
              <option key={queueType} value={queueType}>{queueType}</option>
            ))}
          </select>
        </div>
        <button
          onClick={() => {
            fetchMessages();
            fetchStats();
          }}
          className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Messages Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Message ID</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Type</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Queue</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Status</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Retries</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Created</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-900">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" className="px-4 py-8 text-center text-gray-500">
                    <div className="flex items-center justify-center gap-2">
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      Loading messages...
                    </div>
                  </td>
                </tr>
              ) : messages.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-4 py-8 text-center text-gray-500">
                    No messages found
                  </td>
                </tr>
              ) : (
                messages.map(msg => (
                  <tr key={msg.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900 font-mono text-xs">{msg.id.substring(0, 8)}...</td>
                    <td className="px-4 py-3 text-gray-700">{msg.type}</td>
                    <td className="px-4 py-3">
                      <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                        {msg.queue_type || 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-3 py-1 rounded-full text-xs font-medium border inline-flex items-center gap-1 ${getStatusColor(msg.status)}`}>
                        {getStatusIcon(msg.status)}
                        {msg.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{msg.retry_count || 0}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      {new Date(msg.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleViewDetails(msg.id)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {msg.status === 'FAILED' && (
                          <>
                            <button
                              onClick={() => handleRetry(msg.id)}
                              className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                              title="Retry"
                            >
                              <RefreshCw className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleClear(msg.id)}
                              className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              title="Clear"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {messages.length > 0 && (
          <div className="px-4 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50">
            <div className="text-sm text-gray-600">
              Showing {currentPage * limit + 1} to {Math.min((currentPage + 1) * limit, (messages.length || 0) + currentPage * limit)} messages
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={messages.length < limit}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Message Details Modal */}
      {selectedMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-96 overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Message Details</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-600">ID</label>
                <div className="text-gray-900 font-mono text-xs break-all">{selectedMessage.message?.id}</div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-600">Type</label>
                  <div className="text-gray-900">{selectedMessage.message?.type}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">Status</label>
                  <div className={`inline-block px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(selectedMessage.message?.status)}`}>
                    {selectedMessage.message?.status}
                  </div>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-600">Payload</label>
                <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto max-h-32 text-gray-900">
                  {JSON.stringify(selectedMessage.message?.payload, null, 2)}
                </pre>
              </div>
              {selectedMessage.message?.error && (
                <div>
                  <label className="text-sm font-medium text-red-600">Error</label>
                  <div className="text-red-900 text-sm">{selectedMessage.message.error}</div>
                </div>
              )}
              {selectedMessage.channels && selectedMessage.channels.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-600">Channel Routes</label>
                  <div className="space-y-2">
                    {selectedMessage.channels.map((ch, idx) => (
                      <div key={idx} className="text-xs text-gray-700 p-2 bg-gray-50 rounded">
                        {ch.queue_type} - {ch.status}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {selectedMessage.email_tracking && selectedMessage.email_tracking.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-600">Email Tracking</label>
                  <div className="space-y-2">
                    {selectedMessage.email_tracking.map((et, idx) => (
                      <div key={idx} className="text-xs text-gray-700 p-2 bg-blue-50 rounded border border-blue-200">
                        <div><strong>{et.recipient_email}</strong> - {et.status}</div>
                        {et.opened_at && <div className="text-blue-700">📖 Opened: {new Date(et.opened_at).toLocaleString()}</div>}
                        {et.clicked_at && <div className="text-blue-700">🔗 Clicked: {new Date(et.clicked_at).toLocaleString()}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
              <button
                onClick={() => setSelectedMessage(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueueManagementScreen;
