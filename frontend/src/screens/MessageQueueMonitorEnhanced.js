import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api/client';
import '../styles/MessageQueueMonitorEnhanced.css';

/**
 * Phase 5: Enhanced Message Queue Monitor
 * - Compact/expand queue group toggle
 * - Queue control buttons (pause, resume, retry, purge)
 * - Health metrics from QueueDoctor
 * - Worker status indicator
 */

const MessageQueueMonitorEnhanced = () => {
  const [queueDisplay, setQueueDisplay] = useState(null);
  const [stats, setStats] = useState(null);
  const [healthMetrics, setHealthMetrics] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    fetchQueueData();
    fetchHealthMetrics();
    const interval = setInterval(() => {
      fetchQueueData();
      fetchHealthMetrics();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchQueueData = async () => {
    try {
      const displayData = await apiRequest('/api/v1/message-queue/display', 'GET');
      const statsData = await apiRequest('/api/v1/message-queue/stats', 'GET');

      if (displayData?.data) {
        setQueueDisplay({
          ...displayData.data,
          rows: displayData.data.messages
        });
      }
      if (statsData?.data) {
        setStats(statsData.data);
        setIsPaused(statsData.data.queue_paused || false);
      }
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchHealthMetrics = async () => {
    try {
      const health = await apiRequest('/api/v1/flash/queue-health-pulse', 'GET');
      if (health?.data) {
        setHealthMetrics(health.data);
      }
    } catch (err) {
      console.warn('Could not fetch health metrics:', err);
    }
  };

  const handleToggleGroup = (queueType) => {
    setExpandedGroups(prev => ({
      ...prev,
      [queueType]: !prev[queueType]
    }));
  };

  const handlePauseQueue = async () => {
    try {
      await apiRequest('/api/v1/thunder/pause', { method: 'POST' });
      setIsPaused(true);
      setError(null);
    } catch (err) {
      setError(`Failed to pause queue: ${err.message}`);
    }
  };

  const handleResumeQueue = async () => {
    try {
      await apiRequest('/api/v1/thunder/resume', { method: 'POST' });
      setIsPaused(false);
      setError(null);
    } catch (err) {
      setError(`Failed to resume queue: ${err.message}`);
    }
  };

  const handleBulkRetry = async (queueType) => {
    try {
      await apiRequest(`/api/v1/message-queue/retry-failed?queue_type=${queueType}`, { method: 'POST' });
      await fetchQueueData();
      setError(null);
    } catch (err) {
      setError(`Failed to retry messages: ${err.message}`);
    }
  };

  if (loading) return <div className="queue-loading">Loading queue...</div>;

  return (
    <div className="queue-monitor-enhanced">
      <div className="queue-header">
        <h1>Message Queue Monitor</h1>

        {/* Health Status Indicator */}
        {healthMetrics && (
          <div className={`health-status ${healthMetrics.status}`}>
            <div className="status-dot"></div>
            <span>{healthMetrics.status === 'healthy' ? '✓ Healthy' : '⚠ Degraded'}</span>
          </div>
        )}
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-box">
            <div className="label">Total Messages</div>
            <div className="value">{stats.total_messages}</div>
          </div>
          <div className="stat-box pending">
            <div className="label">Pending</div>
            <div className="value">{stats.pending}</div>
          </div>
          <div className="stat-box failed">
            <div className="label">Failed</div>
            <div className="value">{stats.failed}</div>
          </div>
          {healthMetrics && (
            <>
              <div className="stat-box">
                <div className="label">Processing Rate</div>
                <div className="value">{healthMetrics.processing_rate_per_min.toFixed(1)}/min</div>
              </div>
              <div className="stat-box">
                <div className="label">Success Rate</div>
                <div className="value">{healthMetrics.success_rate.toFixed(1)}%</div>
              </div>
              <div className="stat-box">
                <div className="label">Avg Time</div>
                <div className="value">{healthMetrics.avg_processing_ms}ms</div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Queue Controls */}
      <div className="queue-controls">
        {!isPaused ? (
          <button onClick={handlePauseQueue} className="btn btn-warning">
            ⏸ Pause Queue
          </button>
        ) : (
          <button onClick={handleResumeQueue} className="btn btn-success">
            ▶ Resume Queue
          </button>
        )}
        <span className={`pause-status ${isPaused ? 'paused' : 'running'}`}>
          {isPaused ? 'Queue Paused' : 'Queue Running'}
        </span>
      </div>

      {error && <div className="error-message">⚠ {error}</div>}

      {/* Queue Groups with Compact/Expand */}
      {queueDisplay?.rows && (
        <div className="queue-groups">
          <h3>Operations by Type</h3>
          {(() => {
            const groupedByQueue = {};
            queueDisplay.rows.forEach(row => {
              const queueType = row.type || 'UNKNOWN';
              if (!groupedByQueue[queueType]) groupedByQueue[queueType] = [];
              groupedByQueue[queueType].push(row);
            });

            return Object.entries(groupedByQueue).map(([queueType, rows]) => (
              <div key={queueType} className="queue-group">
                <div className="group-header" onClick={() => handleToggleGroup(queueType)}>
                  <span className="toggle-icon">{expandedGroups[queueType] ? '▼' : '▶'}</span>
                  <h4>{queueType} ({rows.length})</h4>
                  <div className="group-actions">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleBulkRetry(queueType);
                      }}
                      className="btn-sm btn-secondary"
                    >
                      Retry Failed
                    </button>
                  </div>
                </div>

                {expandedGroups[queueType] && (
                  <div className="group-content">
                    <table className="queue-table">
                      <thead>
                        <tr>
                          <th>Message ID</th>
                          <th>Status</th>
                          <th>Created</th>
                          <th>Retries</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map(row => (
                          <tr key={row.id} className={`status-${row.status.toLowerCase()}`}>
                            <td title={row.id}>{row.id.substring(0, 16)}...</td>
                            <td>
                              <span className={`badge badge-${row.status.toLowerCase()}`}>
                                {row.status}
                              </span>
                            </td>
                            <td>{new Date(row.created_at).toLocaleString()}</td>
                            <td>{row.retry_count || 0}</td>
                            <td>
                              {row.status === 'FAILED' && (
                                <button className="btn-sm btn-primary">Retry</button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ));
          })()}
        </div>
      )}
    </div>
  );
};

export default MessageQueueMonitorEnhanced;
