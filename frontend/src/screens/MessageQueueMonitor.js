import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api';
import './MessageQueueMonitor.css';

const MessageQueueMonitor = () => {
  const [queueDisplay, setQueueDisplay] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(5);

  const fetchQueueData = async () => {
    setLoading(true);
    let displayData, statsData;

    try {
      const params = new URLSearchParams();
      if (selectedQueue) params.append('queue_type', selectedQueue);

      try {
        displayData = await apiRequest(`/api/v1/message-queue/display?${params}`, 'GET');
      } catch (err) {
        throw new Error(`Display fetch failed: ${err.message}`);
      }

      try {
        statsData = await apiRequest('/api/v1/message-queue/stats', 'GET');
      } catch (err) {
        throw new Error(`Stats fetch failed: ${err.message}`);
      }

      if (displayData && typeof displayData === 'object') {
        setQueueDisplay(displayData);
      }
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
      }
      setError(null);
    } catch (err) {
      setError(err?.message || 'Error fetching queue data');
      console.error('Queue fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueueData();
    const timer = setInterval(fetchQueueData, refreshInterval * 1000);
    return () => clearInterval(timer);
  }, [selectedQueue, refreshInterval]);

  const getActionBadge = (action) => {
    const actionColors = {
      'CREATE': '#10b981',
      'UPDATE': '#3b82f6',
      'DELETE': '#ef4444',
      'PROCESS': '#8b5cf6',
      'SCHEDULE': '#f59e0b',
      'GENERATE': '#ec4899',
      'ONBOARD': '#06b6d4',
    };
    return { backgroundColor: actionColors[action] || '#6b7280' };
  };

  const getStatusBadge = (status) => {
    const statusColors = {
      'PENDING': '#f59e0b',
      'PROCESSING': '#3b82f6',
      'COMPLETED': '#10b981',
      'FAILED': '#ef4444',
      'RETRYING': '#ec4899',
    };
    return { backgroundColor: statusColors[status] || '#6b7280' };
  };

  if (loading && !queueDisplay) {
    return <div className="queue-loading">Loading queue data...</div>;
  }

  return (
    <div className="queue-monitor">
      <div className="queue-header">
        <h1>Message Queue Monitor</h1>
        <div className="queue-controls">
          <select
            value={selectedQueue || ''}
            onChange={(e) => setSelectedQueue(e.target.value || null)}
            className="queue-filter"
          >
            <option value="">All Queues</option>
            <option value="CANDIDATE_QUEUE">Candidate Queue</option>
            <option value="THUNDER_QUEUE">Thunder Queue</option>
            <option value="EMAIL_QUEUE">Email Queue</option>
            <option value="INTERVIEW_QUEUE">Interview Queue</option>
            <option value="OFFER_QUEUE">Offer Queue</option>
            <option value="ONBOARDING_QUEUE">Onboarding Queue</option>
          </select>
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="refresh-interval"
          >
            <option value="5">Refresh every 5s</option>
            <option value="10">Refresh every 10s</option>
            <option value="30">Refresh every 30s</option>
            <option value="60">Refresh every 60s</option>
          </select>
          <button onClick={fetchQueueData} className="refresh-btn">Refresh Now</button>
        </div>
      </div>

      {error && (
        <div className="error-message">
          Error: {error}
        </div>
      )}

      {stats && (
        <div className="stats-summary">
          <div className="stat-card">
            <div className="stat-label">Total Messages</div>
            <div className="stat-value">{stats.total}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending</div>
            <div className="stat-value pending">{stats.pending_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value failed">{stats.failed_count}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Oldest Pending (sec)</div>
            <div className="stat-value">{stats.oldest_pending_age_seconds || 'N/A'}</div>
          </div>
        </div>
      )}

      {stats && stats.by_queue && (
        <div className="queue-breakdown">
          <h3>Messages by Queue Type</h3>
          <div className="breakdown-list">
            {Object.entries(stats.by_queue).map(([queue, count]) => (
              <div key={queue} className="breakdown-item">
                <span className="queue-name">{queue}</span>
                <span className="message-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {queueDisplay && queueDisplay.rows && (
        <div className="queue-table">
          <h3>Queue Operations (Newest First)</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Queue</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th>Resource ID</th>
                  <th>Created By</th>
                  <th>Created At</th>
                  <th>Retries</th>
                  <th>Preview</th>
                </tr>
              </thead>
              <tbody>
                {queueDisplay.rows.map((row) => (
                  <tr key={row.id} className={`status-${row.status.toLowerCase()}`}>
                    <td>
                      <span className="queue-type">{row.queue_type}</span>
                    </td>
                    <td>
                      <span className="action-badge" style={getActionBadge(row.action)}>
                        {row.action}
                      </span>
                    </td>
                    <td>
                      <span className="status-badge" style={getStatusBadge(row.status)}>
                        {row.status}
                      </span>
                    </td>
                    <td className="resource-id">{row.resource_id || '-'}</td>
                    <td className="created-by">{row.created_by}</td>
                    <td className="timestamp">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="retry-count">{row.retry_count}</td>
                    <td className="preview">
                      {row.payload_preview && Object.keys(row.payload_preview).length > 0 ? (
                        <details>
                          <summary>View</summary>
                          <pre>{JSON.stringify(row.payload_preview, null, 2)}</pre>
                        </details>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {queueDisplay.rows.length === 0 && (
            <div className="empty-state">No messages in queue</div>
          )}
        </div>
      )}
    </div>
  );
};

export default MessageQueueMonitor;
