import { useEffect, useState } from 'react';

const HealthCheckError = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    flexDirection: 'column',
    backgroundColor: '#f5f5f5',
    fontFamily: 'Inter, system-ui, sans-serif',
    color: '#333'
  }}>
    <div style={{ textAlign: 'center', maxWidth: '500px' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '1rem', color: '#d32f2f' }}>
        ⚠️ Backend Service Unavailable
      </h1>
      <p style={{ fontSize: '1.1rem', marginBottom: '1.5rem', color: '#666' }}>
        The backend API server is not running or not responding.
      </p>
      <div style={{
        backgroundColor: 'white',
        padding: '1.5rem',
        borderRadius: '8px',
        marginBottom: '2rem',
        textAlign: 'left',
        border: '1px solid #e0e0e0'
      }}>
        <h3 style={{ marginTop: 0 }}>To fix this:</h3>
        <ol style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
          <li>Start the backend server: <code>python -m uvicorn app.main:app --port 8081</code></li>
          <li>Ensure PostgreSQL is running on localhost:5432</li>
          <li>Check that REACT_APP_API_URL points to the correct backend (currently: {process.env.REACT_APP_API_URL})</li>
          <li>Refresh this page</li>
        </ol>
      </div>
      <button
        onClick={() => window.location.reload()}
        style={{
          padding: '0.75rem 1.5rem',
          fontSize: '1rem',
          backgroundColor: '#F58220',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer'
        }}
      >
        🔄 Try Again
      </button>
    </div>
  </div>
);

export function HealthCheckProvider({ children }) {
  const [isHealthy, setIsHealthy] = useState(null);
  const requireHealthCheck = process.env.REACT_APP_REQUIRE_BACKEND_HEALTH === 'true';
  const apiUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8080';

  useEffect(() => {
    if (!requireHealthCheck) {
      setIsHealthy(true);
      return;
    }

    const checkHealth = async () => {
      try {
        const response = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          timeout: 5000,
        });
        setIsHealthy(response.ok);
      } catch (error) {
        console.error('Backend health check failed:', error);
        setIsHealthy(false);
      }
    };

    checkHealth();
  }, [requireHealthCheck, apiUrl]);

  if (isHealthy === null) {
    // Loading state
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#f5f5f5',
      }}>
        <div style={{ textAlign: 'center' }}>
          {/* BlitzenX Branding with Dynamic X */}
          <div style={{
            marginBottom: '2rem',
            fontSize: '3.5rem',
            fontWeight: '700',
            letterSpacing: '-0.05em',
            fontFamily: 'Inter, system-ui, sans-serif'
          }}>
            <span style={{ color: '#1f2937' }}>Blitzen</span>
            <span style={{
              color: '#F58220',
              display: 'inline-block',
              animation: 'pulse 2s ease-in-out infinite'
            }}>
              X
            </span>
          </div>

          <h2 style={{ color: '#666', marginTop: '1rem', marginBottom: '2rem' }}>
            Initializing innovation...
          </h2>

          <div style={{
            display: 'inline-block',
            width: '40px',
            height: '40px',
            border: '4px solid #f0f0f0',
            borderTop: '4px solid #F58220',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }} />
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
            @keyframes pulse {
              0%, 100% { opacity: 0.7; transform: scale(1); }
              50% { opacity: 1; transform: scale(1.1); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  if (requireHealthCheck && !isHealthy) {
    return <HealthCheckError />;
  }

  return children;
}
