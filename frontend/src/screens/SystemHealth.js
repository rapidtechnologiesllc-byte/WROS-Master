import React, { useState, useEffect } from 'react';
import './SystemHealth.css';

/**
 * System Health Dashboard
 * Displays backend API health status and system information
 * Accessible at /system-health
 */
const SystemHealth = () => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:8081/health');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();

    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchHealth, 10000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="system-health-container">
      <div className="health-card">
        <div className="health-header">
          <h1>🏥 System Health</h1>
          <button
            className="refresh-btn"
            onClick={fetchHealth}
            disabled={loading}
          >
            {loading ? '⟳ Checking...' : '↻ Refresh'}
          </button>
        </div>

        {error && (
          <div className="health-error">
            <span className="status-icon">✗</span>
            <div className="error-content">
              <h3>Backend Unavailable</h3>
              <p>{error}</p>
              <p className="hint">Make sure the backend is running on port 8081</p>
            </div>
          </div>
        )}

        {loading && !health && (
          <div className="health-loading">
            <span className="spinner">⟳</span>
            <p>Checking system health...</p>
          </div>
        )}

        {health && (
          <div className={`health-status ${health.status === 'healthy' ? 'healthy' : 'unhealthy'}`}>
            <div className="status-header">
              <span className="status-icon">
                {health.status === 'healthy' ? '✓' : '✗'}
              </span>
              <div className="status-info">
                <h2>{health.status.toUpperCase()}</h2>
                <p className="status-detail">All systems operational</p>
              </div>
            </div>

            <div className="health-details">
              <div className="detail-row">
                <span className="label">Application:</span>
                <span className="value">{health.app}</span>
              </div>

              <div className="detail-row">
                <span className="label">Version:</span>
                <span className="value">{health.version}</span>
              </div>

              <div className="detail-row">
                <span className="label">Backend URL:</span>
                <span className="value">http://localhost:8081</span>
              </div>

              <div className="detail-row">
                <span className="label">Last Checked:</span>
                <span className="value">{lastChecked}</span>
              </div>
            </div>

            <div className="endpoints-section">
              <h3>Available Endpoints</h3>
              <ul className="endpoints-list">
                <li>
                  <code>GET /health</code>
                  <span>System health status</span>
                </li>
                <li>
                  <code>GET /status/all</code>
                  <span>Complete system status (requires auth)</span>
                </li>
                <li>
                  <code>GET /onboarding/hr/get_all_candidates</code>
                  <span>List all candidates (requires auth)</span>
                </li>
              </ul>
            </div>
          </div>
        )}

        <div className="health-footer">
          <p>Auto-refreshes every 10 seconds</p>
        </div>
      </div>
    </div>
  );
};

export default SystemHealth;
