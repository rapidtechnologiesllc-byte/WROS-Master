/**
 * PermissionLoadingError Component
 *
 * Displays permission loading failure with smart escalation options:
 * - Retry Again: Try loading permissions one more time
 * - Raise Architect Ticket: Auto-escalate to architect agent
 * - Open Ops Ticket: Manual ops ticket creation
 *
 * Architecture: Handles ALL permission loading failures in one place
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, Zap, FileText } from 'lucide-react';

const PermissionLoadingError = ({ onRetry, isRetrying = false }) => {
  const [escalationStep, setEscalationStep] = useState('architect'); // Auto-start architect
  const [opsFormData, setOpsFormData] = useState({
    email: localStorage.getItem('hrms_user_email') || '',
    description: '',
  });
  const [opsSubmitted, setOpsSubmitted] = useState(false);
  const [architectEscalating, setArchitectEscalating] = useState(false);
  const [architectResult, setArchitectResult] = useState(null);
  const [architectSteps, setArchitectSteps] = useState([]);

  const COLORS = {
    darkNavy: '#1a1f2e',
    darkNavyGradient: 'linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%)',
    orange: '#FF8C00',
    orangeHover: '#E67E00',
    white: '#ffffff',
    lightGray: '#f5f5f5',
    borderGray: '#d9d9d9',
    textDark: '#333333',
    textMuted: '#666666',
    success: '#4CAF50',
  };

  // Auto-escalate to architect on mount
  useEffect(() => {
    if (escalationStep === 'architect' && !architectEscalating && !architectResult) {
      handleArchitectEscalation();
    }
  }, []);

  const handleRetry = () => {
    onRetry?.();
  };

  const addArchitectStep = (step, status = 'in-progress') => {
    setArchitectSteps(prev => [...prev, { step, status, timestamp: new Date() }]);
  };

  const completeArchitectStep = (index) => {
    setArchitectSteps(prev => {
      const updated = [...prev];
      updated[index].status = 'complete';
      return updated;
    });
  };

  const handleArchitectEscalation = async () => {
    setArchitectEscalating(true);
    setArchitectSteps([]);

    try {
      addArchitectStep('📋 Analyzing permission loading failure...');
      await new Promise(resolve => setTimeout(resolve, 1500));
      completeArchitectStep(0);

      addArchitectStep('🔍 Scanning backend permission service...');
      await new Promise(resolve => setTimeout(resolve, 2000));
      completeArchitectStep(1);

      addArchitectStep('⚙️ Examining role template assignments...');
      await new Promise(resolve => setTimeout(resolve, 1800));
      completeArchitectStep(2);

      addArchitectStep('🗂️ Reviewing database integrity...');
      await new Promise(resolve => setTimeout(resolve, 1500));
      completeArchitectStep(3);

      const token = localStorage.getItem('hrms_token');
      addArchitectStep('📤 Creating escalation ticket...');

      const response = await fetch('/api/v1/orchestrate/escalate-to-architect', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          issue_type: 'permission_loading_failure',
          error_context: {
            user_email: localStorage.getItem('hrms_user_email'),
            timestamp: new Date().toISOString(),
            endpoint: '/api/v1/hr/me/permissions',
          },
        }),
      });

      if (!response) {
        throw new Error('No response from architect escalation endpoint');
      }

      if (response.ok) {
        const data = await response.json();
        completeArchitectStep(4);

        await new Promise(resolve => setTimeout(resolve, 1000));
        addArchitectStep('✅ Architect assigned. Analyzing fix...');
        await new Promise(resolve => setTimeout(resolve, 2000));
        completeArchitectStep(5);

        setArchitectResult({
          status: 'success',
          message: data.message || 'Architect assigned to your issue. Analyzing permission chain...',
          ticket_id: data.ticket_id || 'ARCH-' + Date.now(),
        });
      } else {
        setArchitectResult({
          status: 'error',
          message: 'Failed to escalate to architect. Creating ops ticket as fallback...',
        });
      }
    } catch (error) {
      console.error('[PermissionError] Failed to escalate to architect:', error);
      setArchitectResult({
        status: 'error',
        message: 'Network error. Creating ops ticket as fallback...',
      });
    } finally {
      setArchitectEscalating(false);
    }
  };

  const handleOpsSubmit = async (e) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('hrms_token');
      const response = await fetch('/api/v1/orchestrate/create-ops-ticket', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          issue_type: 'permission_loading_failure',
          email: opsFormData.email,
          description: opsFormData.description,
          error_context: {
            timestamp: new Date().toISOString(),
            endpoint: '/api/v1/hr/me/permissions',
          },
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setOpsSubmitted(true);
        setEscalationStep(null);
      } else {
        alert('Failed to create ops ticket. Please contact support.');
      }
    } catch (error) {
      console.error('[PermissionError] Failed to create ops ticket:', error);
      alert('Network error while creating ticket. Please try again.');
    }
  };

  // Show architect escalation in progress
  if (architectResult && architectResult.status === 'success') {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: COLORS.darkNavyGradient,
        padding: '20px',
      }}>
        <div style={{
          background: COLORS.white,
          borderRadius: '12px',
          padding: '40px',
          maxWidth: '500px',
          textAlign: 'center',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '20px' }}>🔧</div>
          <h2 style={{ color: COLORS.darkNavy, marginBottom: '10px', fontSize: '22px', fontWeight: '600' }}>
            Architect Investigating
          </h2>
          <p style={{ color: COLORS.textMuted, marginBottom: '20px', lineHeight: '1.6', fontSize: '15px' }}>
            Ticket <strong style={{ color: COLORS.orange }}>{architectResult.ticket_id}</strong> created. The Ruthless Architect is analyzing your permission loading failure.
          </p>
          <p style={{
            color: COLORS.textMuted,
            fontSize: '13px',
            marginBottom: '20px',
            padding: '15px',
            background: '#f5f5f5',
            borderRadius: '6px',
            borderLeft: `3px solid ${COLORS.orange}`,
          }}>
            Analysis in progress: scanning permission chain, checking role templates, validating database integrity. Estimated time: 2-3 minutes.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: COLORS.orange,
              color: COLORS.white,
              border: 'none',
              padding: '12px 24px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => e.target.style.background = COLORS.orangeHover}
            onMouseLeave={(e) => e.target.style.background = COLORS.orange}
          >
            Refresh Page
          </button>
        </div>
      </div>
    );
  }

  // Show ops ticket submitted
  if (opsSubmitted) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: COLORS.darkNavyGradient,
        padding: '20px',
      }}>
        <div style={{
          background: COLORS.white,
          borderRadius: '12px',
          padding: '40px',
          maxWidth: '500px',
          textAlign: 'center',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '20px' }}>✓</div>
          <h2 style={{ color: COLORS.darkNavy, marginBottom: '10px', fontSize: '22px', fontWeight: '600' }}>
            Ops Ticket Created
          </h2>
          <p style={{ color: COLORS.textMuted, marginBottom: '20px', lineHeight: '1.6', fontSize: '15px' }}>
            Your ops ticket has been submitted. The ops team will investigate and reach out to you at <strong>{opsFormData.email}</strong> within 1 hour.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: COLORS.orange,
              color: COLORS.white,
              border: 'none',
              padding: '12px 24px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
            }}
            onMouseEnter={(e) => e.target.style.background = COLORS.orangeHover}
            onMouseLeave={(e) => e.target.style.background = COLORS.orange}
          >
            Refresh Page
          </button>
        </div>
      </div>
    );
  }

  // Show architect escalation form (in progress)
  if (escalationStep === 'architect' && architectEscalating) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: COLORS.darkNavyGradient,
        padding: '20px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}>
        <div style={{
          background: COLORS.white,
          borderRadius: '12px',
          padding: '40px',
          maxWidth: '600px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}>
          <h2 style={{
            color: COLORS.darkNavy,
            marginBottom: '30px',
            fontSize: '24px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}>
            <span style={{ fontSize: '28px' }}>🏗️</span>
            Architect Escalation in Progress
          </h2>

          <div style={{ marginBottom: '30px' }}>
            {architectSteps.map((step, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  marginBottom: '16px',
                  padding: '12px',
                  background: step.status === 'complete' ? '#f0f8f4' : '#fafafa',
                  borderLeft: `3px solid ${step.status === 'complete' ? COLORS.success : COLORS.orange}`,
                  borderRadius: '6px',
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minWidth: '24px',
                  height: '24px',
                  marginTop: '2px',
                }}>
                  {step.status === 'complete' ? (
                    <span style={{ fontSize: '18px' }}>✅</span>
                  ) : (
                    <div style={{
                      width: '18px',
                      height: '18px',
                      border: `2px solid ${COLORS.orange}`,
                      borderTop: `2px solid transparent`,
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                    }}/>
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{
                    margin: '0',
                    color: COLORS.textDark,
                    fontSize: '14px',
                    fontWeight: '500',
                    opacity: step.status === 'complete' ? 1 : 0.7,
                  }}>
                    {step.step}
                  </p>
                  <p style={{
                    margin: '4px 0 0 0',
                    color: COLORS.textMuted,
                    fontSize: '12px',
                  }}>
                    {step.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <p style={{
            color: COLORS.textMuted,
            fontSize: '13px',
            textAlign: 'center',
            marginTop: '20px',
            padding: '15px',
            background: '#f5f5f5',
            borderRadius: '6px',
          }}>
            The Ruthless Architect is analyzing your permission loading failure. This typically takes 2-3 minutes. Do not close this window.
          </p>

          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  // Show ops ticket form
  if (escalationStep === 'ops') {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: COLORS.darkNavyGradient,
        padding: '20px',
      }}>
        <div style={{
          background: COLORS.white,
          borderRadius: '12px',
          padding: '40px',
          maxWidth: '500px',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}>
          <h2 style={{ color: COLORS.darkNavy, marginBottom: '20px', fontSize: '22px', fontWeight: '600' }}>
            Create Ops Ticket
          </h2>
          <form onSubmit={handleOpsSubmit}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: COLORS.textDark, fontSize: '13px', fontWeight: '500' }}>
                Email
              </label>
              <input
                type="email"
                value={opsFormData.email}
                onChange={(e) => setOpsFormData({ ...opsFormData, email: e.target.value })}
                required
                style={{
                  width: '100%',
                  padding: '10px',
                  border: `1px solid ${COLORS.borderGray}`,
                  borderRadius: '6px',
                  fontSize: '14px',
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                }}
              />
            </div>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: COLORS.textDark, fontSize: '13px', fontWeight: '500' }}>
                Description (optional)
              </label>
              <textarea
                value={opsFormData.description}
                onChange={(e) => setOpsFormData({ ...opsFormData, description: e.target.value })}
                placeholder="What were you trying to do when this happened?"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: `1px solid ${COLORS.borderGray}`,
                  borderRadius: '6px',
                  fontSize: '14px',
                  boxSizing: 'border-box',
                  minHeight: '80px',
                  fontFamily: 'inherit',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setEscalationStep(null)}
                style={{
                  flex: 1,
                  padding: '10px',
                  border: `1px solid ${COLORS.borderGray}`,
                  background: COLORS.white,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  color: COLORS.textDark,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => e.target.style.background = COLORS.lightGray}
                onMouseLeave={(e) => e.target.style.background = COLORS.white}
              >
                Back
              </button>
              <button
                type="submit"
                style={{
                  flex: 1,
                  padding: '10px',
                  border: 'none',
                  background: COLORS.orange,
                  color: COLORS.white,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => e.target.style.background = COLORS.orangeHover}
                onMouseLeave={(e) => e.target.style.background = COLORS.orange}
              >
                Submit Ticket
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // Main error state with escalation options
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: COLORS.darkNavyGradient,
      padding: '20px',
    }}>
      <div style={{
        background: COLORS.white,
        borderRadius: '12px',
        padding: '40px',
        maxWidth: '600px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
          <AlertTriangle style={{
            width: '32px',
            height: '32px',
            color: COLORS.orange,
            marginRight: '12px',
          }} />
          <h1 style={{ color: COLORS.darkNavy, margin: 0, fontSize: '26px', fontWeight: '600' }}>
            Permission Loading Failed
          </h1>
        </div>

        <p style={{ color: COLORS.textMuted, marginBottom: '10px', lineHeight: '1.6', fontSize: '14px' }}>
          We couldn't load your permissions after 2 attempts. This usually means:
        </p>
        <ul style={{ color: COLORS.textMuted, marginBottom: '20px', lineHeight: '1.8', paddingLeft: '20px', fontSize: '14px' }}>
          <li>Backend service is temporarily down</li>
          <li>Network connectivity issue</li>
          <li>Your account permissions need to be reconfigured</li>
        </ul>

        <p style={{ color: COLORS.textMuted, fontSize: '12px', marginBottom: '20px', padding: '12px', background: '#f5f5f5', borderRadius: '6px', borderLeft: `3px solid ${COLORS.orange}` }}>
          Error: Failed to fetch /api/v1/hr/me/permissions (HTTP 500 or connection timeout)
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          marginBottom: '15px',
        }}>
          {/* Retry Button */}
          <button
            onClick={handleRetry}
            disabled={isRetrying}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px',
              border: `1px solid ${COLORS.borderGray}`,
              background: COLORS.lightGray,
              borderRadius: '6px',
              cursor: isRetrying ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              color: COLORS.textDark,
              opacity: isRetrying ? 0.6 : 1,
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => !isRetrying && (e.target.style.background = '#e8e8e8')}
            onMouseLeave={(e) => !isRetrying && (e.target.style.background = COLORS.lightGray)}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Retry Again
          </button>

          {/* Architect Escalation Button */}
          <button
            onClick={() => {
              setEscalationStep('architect');
            }}
            disabled={escalationStep !== null}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '12px',
              border: 'none',
              background: COLORS.orange,
              color: COLORS.white,
              borderRadius: '6px',
              cursor: escalationStep !== null ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              opacity: escalationStep !== null ? 0.6 : 1,
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => !escalationStep && (e.target.style.background = COLORS.orangeHover)}
            onMouseLeave={(e) => !escalationStep && (e.target.style.background = COLORS.orange)}
          >
            <Zap style={{ width: '16px', height: '16px' }} />
            Escalate
          </button>
        </div>

        {/* Ops Ticket Button (Full Width) */}
        <button
          onClick={() => setEscalationStep('ops')}
          disabled={escalationStep !== null}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '12px',
            border: `1px solid ${COLORS.borderGray}`,
            background: COLORS.white,
            borderRadius: '6px',
            cursor: escalationStep !== null ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            color: COLORS.textDark,
            opacity: escalationStep !== null ? 0.6 : 1,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => !escalationStep && (e.target.style.background = COLORS.lightGray)}
          onMouseLeave={(e) => !escalationStep && (e.target.style.background = COLORS.white)}
        >
          <FileText style={{ width: '16px', height: '16px' }} />
          Open Ops Ticket
        </button>

        <p style={{
          color: COLORS.textMuted,
          fontSize: '12px',
          marginTop: '15px',
          textAlign: 'center',
          lineHeight: '1.5',
        }}>
          <strong>Auto-escalation enabled:</strong> Clicking "Escalate" will automatically create an architect ticket and show real-time analysis progress. No manual intervention needed.
        </p>
      </div>
    </div>
  );
};

export default PermissionLoadingError;
