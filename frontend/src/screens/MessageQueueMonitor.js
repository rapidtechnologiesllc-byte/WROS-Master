import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api/client';
import './MessageQueueMonitor.css';

const MessageQueueMonitor = () => {
  const [queueDisplay, setQueueDisplay] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(5);
  const [queueTypes, setQueueTypes] = useState([]);

  const fetchQueueTypes = async () => {
    try {
      const response = await apiRequest('/api/v1/config/queue-types', 'GET');
      setQueueTypes(response.queue_types || []);
    } catch (err) {
      console.error('Failed to load queue types:', err);
      setQueueTypes([]);
      throw err;
    }
  };

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

      if (displayData?.data && typeof displayData.data === 'object') {
        // Backend returns 'messages', component expects 'rows'
        const normalized = {
          ...displayData.data,
          rows: displayData.data.messages
        };
        setQueueDisplay(normalized);
      }
      if (statsData?.data && typeof statsData.data === 'object') {
        setStats(statsData.data);
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
    (async () => {
      try {
        await fetchQueueTypes();
      } catch (err) {
        console.error('Failed to fetch queue types:', err);
      }
      try {
        await fetchQueueData();
      } catch (err) {
        console.error('Failed to fetch queue data:', err);
      }
    })();

    const timer = setInterval(() => {
      (async () => {
        try {
          await fetchQueueData();
        } catch (err) {
          console.error('Failed to fetch queue data:', err);
        }
      })();
    }, refreshInterval * 1000);

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
            {queueTypes.map(queueType => (
              <option key={queueType} value={queueType}>{queueType}</option>
            ))}
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
            <div className="stat-value">{stats.total_messages}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending</div>
            <div className="stat-value pending">{stats.pending}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value failed">{stats.failed}</div>
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
          <h3>Queue Operations by Type (Newest First)</h3>
          {(() => {
            const groupedByQueue = {};
            queueDisplay.rows.forEach(row => {
              const queueType = row.type || 'UNKNOWN';
              if (!groupedByQueue[queueType]) {
                groupedByQueue[queueType] = [];
              }
              groupedByQueue[queueType].push(row);
            });

            return Object.entries(groupedByQueue).map(([queueType, rows]) => (
              <div key={queueType} className="queue-group">
                <h4>{queueType} ({rows.length})</h4>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Created At</th>
                        <th>Completed At</th>
                        <th>Retries</th>
                        <th>Error</th>
                        <th>Preview</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.id} className={`status-${row.status.toLowerCase()}`}>
                          <td>
                            <span className="queue-type">{row.type}</span>
                          </td>
                          <td>
                            <span className="status-badge" style={getStatusBadge(row.status)}>
                              {row.status}
                            </span>
                          </td>
                          <td className="timestamp">
                            {new Date(row.created_at).toLocaleString()}
                          </td>
                          <td className="timestamp">
                            {row.completed_at ? new Date(row.completed_at).toLocaleString() : '-'}
                          </td>
                          <td className="retry-count">{row.retry_count || 0}</td>
                          <td className="error-message">
                            {row.error ? (
                              <details>
                                <summary>Error</summary>
                                <pre>{row.error}</pre>
                              </details>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="preview">
                            {row.payload ? (
                              <details>
                                <summary>View</summary>
                                <pre>{JSON.stringify(row.payload, null, 2)}</pre>
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
              </div>
            ));
          })()}
          {queueDisplay.rows.length === 0 && (
            <div className="empty-state">No messages in queue</div>
          )}
        </div>
      )}
    </div>
  );
};

export default MessageQueueMonitor;
