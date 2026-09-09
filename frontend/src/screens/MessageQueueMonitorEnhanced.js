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
  const [expandedPayloads, setExpandedPayloads] = useState({});
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

  const handleTogglePayload = (messageId) => {
    setExpandedPayloads(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
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

            return Object.entries(groupedByQueue).map(([queueType, rows]) => {
              const queueStats = {
                pending: rows.filter(r => r.status === 'PENDING').length,
                processing: rows.filter(r => r.status === 'PROCESSING').length,
                failed: rows.filter(r => r.status === 'FAILED').length,
                completed: rows.filter(r => r.status === 'COMPLETED').length
              };
              return (
              <div key={queueType} className="queue-group">
                <div className="group-header" onClick={() => handleToggleGroup(queueType)}>
                  <span className="toggle-icon">{expandedGroups[queueType] ? '▼' : '▶'}</span>
                  <h4>{queueType} ({rows.length})</h4>

                  {/* Per-Queue Stats - Column Display */}
                  <div className="queue-type-stats">
                    <div className="stat-column">
                      <div className="stat-label">PENDING</div>
                      <div className="stat-value pending">{queueStats.pending}</div>
                    </div>
                    <div className="stat-column">
                      <div className="stat-label">PROCESSING</div>
                      <div className="stat-value processing">{queueStats.processing}</div>
                    </div>
                    <div className="stat-column">
                      <div className="stat-label">FAILED</div>
                      <div className="stat-value failed">{queueStats.failed}</div>
                    </div>
                    <div className="stat-column">
                      <div className="stat-label">COMPLETED</div>
                      <div className="stat-value completed">{queueStats.completed}</div>
                    </div>
                  </div>

                  {/* Per-Queue Controls */}
                  <div className="queue-type-controls">
                    {!isPaused ? (
                      <button onClick={(e) => { e.stopPropagation(); handlePauseQueue(); }} className="btn-sm btn-warning">
                        ⏸ Pause
                      </button>
                    ) : (
                      <button onClick={(e) => { e.stopPropagation(); handleResumeQueue(); }} className="btn-sm btn-success">
                        ▶ Resume
                      </button>
                    )}
                    <span className={`queue-status ${isPaused ? 'paused' : 'running'}`}>
                      {isPaused ? 'Paused' : 'Running'}
                    </span>
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
                          <th style={{width: '12%'}}>Message ID</th>
                          <th style={{width: '8%'}}>Status</th>
                          <th style={{width: '12%'}}>Created</th>
                          <th style={{width: '6%'}}>Retries</th>
                          <th style={{width: '25%'}}>Error Message</th>
                          <th style={{width: '25%'}}>Doctor's Advice</th>
                          <th style={{width: '12%'}}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map(row => (
                          <React.Fragment key={row.id}>
                            <tr className={`status-${row.status.toLowerCase()}`}>
                              <td title={row.id} style={{width: '12%'}}>
                                <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                                  <button
                                    onClick={() => handleTogglePayload(row.id)}
                                    style={{background: 'none', border: 'none', cursor: 'pointer', padding: '4px', fontSize: '12px'}}
                                  >
                                    {expandedPayloads[row.id] ? '▼' : '▶'}
                                  </button>
                                  <span title={row.id}>{row.id.substring(0, 12)}...</span>
                                </div>
                              </td>
                              <td style={{width: '8%'}}>
                                <span className={`badge badge-${row.status.toLowerCase()}`}>
                                  {row.status}
                                </span>
                              </td>
                              <td style={{width: '12%'}}>{new Date(row.created_at).toLocaleString()}</td>
                              <td style={{width: '6%', fontWeight: 'bold', color: row.retry_count > 0 ? '#f59e0b' : '#000'}}>
                                {row.retry_count || 0}
                              </td>
                              <td style={{width: '25%', maxHeight: '80px', overflow: 'auto', whiteSpace: 'normal', wordBreak: 'break-word'}}>
                                <span className="error-text" title={row.error || 'None'}>
                                  {row.error ? row.error.substring(0, 100) + (row.error.length > 100 ? '...' : '') : '-'}
                                </span>
                              </td>
                              <td style={{width: '25%', maxHeight: '80px', overflow: 'auto', whiteSpace: 'normal', wordBreak: 'break-word', fontSize: '12px', color: '#666'}}>
                                <span className="doctor-advice">
                                  {(() => {
                                    if (row.status === 'FAILED') {
                                      if (row.retry_count >= 5) {
                                        return '❌ Max retries exceeded - manual review required';
                                      } else {
                                        return `🔄 Scheduled for retry (Attempt ${(row.retry_count || 0) + 1}/5)`;
                                      }
                                    } else if (row.status === 'PENDING') {
                                      return '⏳ Queued for processing';
                                    } else if (row.status === 'PROCESSING') {
                                      return '⚙️ Currently processing...';
                                    } else {
                                      return '✅ Successfully processed';
                                    }
                                  })()}
                                </span>
                              </td>
                              <td style={{width: '12%'}}>
                                {row.status === 'FAILED' && (
                                  <button className="btn-sm btn-primary">Retry</button>
                                )}
                              </td>
                            </tr>
                            {expandedPayloads[row.id] && (
                              <tr className={`status-${row.status.toLowerCase()}`}>
                                <td colSpan="7" style={{padding: '12px', background: '#f9fafb', borderTop: '1px solid #e5e7eb'}}>
                                  <div style={{fontSize: '12px'}}>
                                    <div style={{fontWeight: '600', marginBottom: '8px', color: '#1a1a1a'}}>Message Payload:</div>
                                    <pre style={{
                                      background: '#1a1a1a',
                                      color: '#00ff00',
                                      padding: '12px',
                                      borderRadius: '4px',
                                      overflow: 'auto',
                                      maxHeight: '300px',
                                      fontSize: '11px',
                                      fontFamily: 'monospace'
                                    }}>
                                      {JSON.stringify(row.payload || {}, null, 2)}
                                    </pre>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
            });
          })()}
        </div>
      )}
    </div>
  );
};

export default MessageQueueMonitorEnhanced;
