import React, { useState } from 'react';
import './AuditTrail.css';

const AuditTrail = ({ logs = [] }) => {
  const [expandedId, setExpandedId] = useState(null);

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatJson = (jsonString) => {
    try {
      if (!jsonString) return null;
      return typeof jsonString === 'string' ? JSON.parse(jsonString) : jsonString;
    } catch (e) {
      return jsonString;
    }
  };

  const getActionIcon = (action) => {
    const icons = {
      create: '➕',
      update: '✏️',
      delete: '🗑️',
      grant: '✅',
      revoke: '❌',
      assign: '🔗',
      remove: '⛔',
    };
    return icons[action] || '📝';
  };

  const getActionColor = (action) => {
    if (action === 'delete' || action === 'revoke' || action === 'remove') return 'danger';
    if (action === 'create' || action === 'grant' || action === 'assign') return 'success';
    return 'info';
  };

  if (!logs || logs.length === 0) {
    return (
      <div className="audit-trail-empty">
        <div className="empty-icon">📋</div>
        <p>No changes recorded yet</p>
      </div>
    );
  }

  return (
    <div className="audit-trail">
      <div className="trail-stats">
        <div className="stat">
          <span className="stat-label">Total Changes</span>
          <span className="stat-value">{logs.length}</span>
        </div>
      </div>

      <div className="trail-timeline">
        {logs.map((log, idx) => (
          <div key={idx} className={`timeline-item ${getActionColor(log.action)}`}>
            <div className="timeline-marker">
              <span className="marker-icon">{getActionIcon(log.action)}</span>
            </div>

            <div className="timeline-content">
              <button
                className="timeline-header"
                onClick={() => setExpandedId(expandedId === idx ? null : idx)}
              >
                <span className="action-badge">{log.action.toUpperCase()}</span>
                <span className="time">{formatDate(log.timestamp)}</span>
                <span className="user">{log.user_id || 'System'}</span>
                <span className="toggle">{expandedId === idx ? '▼' : '▶'}</span>
              </button>

              {expandedId === idx && (
                <div className="timeline-details">
                  {log.old_value && (
                    <div className="detail-section">
                      <h5>Before</h5>
                      <pre className="detail-json">
                        {JSON.stringify(formatJson(log.old_value), null, 2)}
                      </pre>
                    </div>
                  )}

                  {log.new_value && (
                    <div className="detail-section">
                      <h5>After</h5>
                      <pre className="detail-json">
                        {JSON.stringify(formatJson(log.new_value), null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="detail-section meta">
                    <div className="meta-item">
                      <span className="meta-label">Entity Type:</span>
                      <code>{log.entity_type}</code>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Entity ID:</span>
                      <code>{log.entity_id}</code>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="trail-legend">
        <div className="legend-item success">
          <span className="legend-icon">✅</span>
          <span>Creation/Grant</span>
        </div>
        <div className="legend-item danger">
          <span className="legend-icon">🗑️</span>
          <span>Deletion/Revoke</span>
        </div>
        <div className="legend-item info">
          <span className="legend-icon">✏️</span>
          <span>Update</span>
        </div>
      </div>
    </div>
  );
};

export default AuditTrail;
