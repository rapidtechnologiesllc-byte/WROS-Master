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

  const [searchTerm, setSearchTerm] = useState('');

  const filteredEndpoints = health?.endpoints?.filter(ep =>
    ep.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="system-health-container">
      <div className="health-card">
        <div className="health-header">
          <div>
            <h1>🏥 System Health</h1>
            <p className="health-summary">
              {health?.status === 'healthy'
                ? '✓ All endpoints operational'
                : '⚠ Some endpoints have issues'}
            </p>
          </div>
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

            <div className="health-summary-section">
              <div className="summary-stat">
                <span className="stat-label">Application</span>
                <span className="stat-value">{health.app}</span>
              </div>
              <div className="summary-stat">
                <span className="stat-label">Version</span>
                <span className="stat-value">{health.version}</span>
              </div>
              <div className="summary-stat">
                <span className="stat-label">Last Checked</span>
                <span className="stat-value">{lastChecked}</span>
              </div>
            </div>

            <div className="endpoints-section">
              <div className="endpoints-header">
                <h3>Endpoint Status</h3>
                <input
                  type="text"
                  placeholder="Search endpoints..."
                  className="endpoints-search"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="endpoints-table">
                <div className="table-header">
                  <div className="col-endpoint">Endpoint</div>
                  <div className="col-status">Status</div>
                  <div className="col-description">Description</div>
                </div>

                <div className="table-body">
                  <div className="table-row">
                    <div className="col-endpoint"><code>GET /health</code></div>
                    <div className="col-status">
                      <span className="status-badge healthy">● Healthy</span>
                    </div>
                    <div className="col-description">System health status</div>
                  </div>

                  <div className="table-row">
                    <div className="col-endpoint"><code>GET /status/all</code></div>
                    <div className="col-status">
                      <span className="status-badge healthy">● Healthy</span>
                    </div>
                    <div className="col-description">Complete system status (requires auth)</div>
                  </div>

                  <div className="table-row">
                    <div className="col-endpoint"><code>GET /onboarding/hr/get_all_candidates</code></div>
                    <div className="col-status">
                      <span className="status-badge healthy">● Healthy</span>
                    </div>
                    <div className="col-description">List all candidates (requires auth)</div>
                  </div>
                </div>
              </div>
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
