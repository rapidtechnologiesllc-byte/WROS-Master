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
      const response = await apiRequest('/api/v1/message-queue/types', 'GET');
      setQueueTypes(response.queue_types || []);
    } catch (err) {
      console.error('Failed to load queue types:', err);
      setQueueTypes([]);
      throw err;
    }
  };

  const fetchQueueData = async () => {
    setLoading(true);

    try {
      const params = new URLSearchParams();
      if (selectedQueue) params.append('message_type', selectedQueue);

      const displayData = await apiRequest(`/api/v1/message-queue/display?${params}`, 'GET');

      if (displayData && typeof displayData === 'object') {
        // Backend returns 'messages' and 'status_counts'
        const normalized = {
          messages: displayData.messages || [],
          total: displayData.total || 0,
          status_counts: displayData.status_counts || {}
        };
        setQueueDisplay(normalized);
        setStats(displayData.status_counts || {});
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

  const handleRetry = async (messageId) => {
    try {
      setError(null);
      await apiRequest(`/api/v1/message-queue/${messageId}/retry`, 'POST');
      // Refresh queue data after retry
      await fetchQueueData();
    } catch (err) {
      setError(`Failed to retry message: ${err.message}`);
    }
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
            <div className="stat-value">{queueDisplay?.total || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Pending</div>
            <div className="stat-value pending">{stats.pending || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Processing</div>
            <div className="stat-value processing">{stats.processing || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Completed</div>
            <div className="stat-value completed">{stats.completed || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value failed">{stats.failed || 0}</div>
          </div>
        </div>
      )}

      {queueDisplay && queueDisplay.messages && queueDisplay.messages.length > 0 && (
        <div className="queue-table">
          <h3>Queue Messages (Newest First)</h3>
          {(() => {
            const groupedByQueue = {};
            queueDisplay.messages.forEach(row => {
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
                        <th style={{width: '20%'}}>Message ID</th>
                        <th style={{width: '10%'}}>Status</th>
                        <th style={{width: '15%'}}>Created At</th>
                        <th style={{width: '15%'}}>Completed At</th>
                        <th style={{width: '8%'}}>Retries</th>
                        <th style={{width: '20%'}}>Error</th>
                        <th style={{width: '12%'}}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.id} className={`status-${row.status.toLowerCase()}`}>
                          <td style={{width: '20%'}}>
                            <span className="message-id" title={row.id}>{row.id.substring(0, 12)}...</span>
                          </td>
                          <td style={{width: '10%'}}>
                            <span className="status-badge" style={getStatusBadge(row.status)}>
                              {row.status}
                            </span>
                          </td>
                          <td style={{width: '15%'}} className="timestamp">
                            {new Date(row.created_at).toLocaleString()}
                          </td>
                          <td style={{width: '15%'}} className="timestamp">
                            {row.completed_at ? new Date(row.completed_at).toLocaleString() : '-'}
                          </td>
                          <td style={{width: '8%'}} className="retry-count">{row.retry_count || 0}</td>
                          <td style={{width: '20%', wordBreak: 'break-word', maxHeight: '100px', overflow: 'auto'}} className="error-message">
                            {row.error ? (
                              <details>
                                <summary style={{cursor: 'pointer', color: '#ef4444', fontWeight: 'bold'}}>
                                  Error ({row.error.length > 50 ? '...' : ''})
                                </summary>
                                <pre style={{fontSize: '11px', margin: '8px 0', padding: '8px', backgroundColor: '#f5f5f5', borderRadius: '4px', whiteSpace: 'pre-wrap', wordWrap: 'break-word', wordBreak: 'break-word', maxWidth: '1200px', maxHeight: '300px', overflow: 'auto'}}>{row.error}</pre>
                              </details>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td style={{width: '12%'}}>
                            {row.status === 'FAILED' ? (
                              <button
                                onClick={() => handleRetry(row.id)}
                                style={{
                                  padding: '6px 12px',
                                  backgroundColor: '#3b82f6',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '12px'
                                }}
                              >
                                Retry
                              </button>
                            ) : row.payload ? (
                              <details>
                                <summary style={{cursor: 'pointer', color: '#3b82f6'}}>View</summary>
                                <pre style={{fontSize: '11px', margin: '8px 0', padding: '8px', backgroundColor: '#f5f5f5', maxHeight: '200px', overflow: 'auto'}}>{JSON.stringify(row.payload, null, 2)}</pre>
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
