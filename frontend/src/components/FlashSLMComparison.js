import { apiFetch } from "../services/api/client";
/**Phase 3: Flash vs SLM Comparison Component
 *
 * Displays Flash interview assessment vs SLM candidate metrics side-by-side.
 * Shows conflicts, agreement level, and next-action recommendations.
 * Responsive design for mobile/tablet/desktop.
 *
 * @component
 * @example
 * return <FlashSLMComparison candidateId="cand-123" interviewId="int-456" />
 *
 * @param {string} candidateId - Required candidate UUID
 * @param {string} [interviewId] - Optional specific interview UUID; uses latest if omitted
 * @returns {React.ReactElement}
 */

import React, { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import './FlashSLMComparison.css';

const COMPARISON_CACHE = {};
const FETCH_TIMEOUT_MS = 30000;

/**
 * Safe date parsing across browsers
 * @param {string} isoString - ISO date string
 * @returns {Date|null}
 */
const parseISODate = (isoString) => {
  if (!isoString) return null;
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return null;
    return date;
  } catch {
    return null;
  }
};

const FlashSLMComparison = ({ candidateId, interviewId }) => {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);
  const timeoutIdRef = useRef(null);

  // Validate props (HIGH-12)
  useEffect(() => {
    if (!candidateId || typeof candidateId !== 'string') {
      setError('Invalid candidateId prop');
      setLoading(false);
      return;
    }
    if (interviewId && typeof interviewId !== 'string') {
      setError('Invalid interviewId prop');
      setLoading(false);
      return;
    }
  }, [candidateId, interviewId]);

  useEffect(() => {
    fetchComparison();

    return () => {
      // Cleanup: abort in-flight request and clear timeout (CRITICAL-3, CRITICAL-4)
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
      }
    };
  }, [candidateId, interviewId]);

  const fetchComparison = async () => {
    if (!candidateId) return;

    try {
      // Validate interview ID (CRITICAL-14)
      if (interviewId && !/^[a-zA-Z0-9_-]{1,255}$/.test(interviewId)) {
        throw new Error('Invalid interview ID format');
      }

      // Check cache first (MEDIUM-3)
      const cacheKey = `${candidateId}_${interviewId || 'latest'}`;
      if (COMPARISON_CACHE[cacheKey]) {
        setComparison(COMPARISON_CACHE[cacheKey]);
        setLoading(false);
        return;
      }

      setLoading(true);

      const url = `/api/v1/candidates/${candidateId}/flash-slm-comparison${interviewId ? `?interview_id=${interviewId}` : ''}`;

      // Setup abort controller for race condition prevention (CRITICAL-3)
      abortControllerRef.current = new AbortController();

      // Setup timeout (CRITICAL-4)
      timeoutIdRef.current = setTimeout(
        () => abortControllerRef.current?.abort(),
        FETCH_TIMEOUT_MS
      );

      const response = await fetch(url, {
        signal: abortControllerRef.current.signal,
      });

      clearTimeout(timeoutIdRef.current);

      if (!response.ok) {
        const status = response.status;
        if (status === 404) {
          throw new Error('Candidate or comparison data not found');
        } else if (status === 400) {
          throw new Error('Invalid request - missing required analysis data');
        } else {
          throw new Error(`API error: ${status}`);
        }
      }

      const data = await response.json();

      // Validate response structure (CRITICAL-5)
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid response format from server');
      }

      // Cache result
      COMPARISON_CACHE[cacheKey] = data;

      setComparison(data);
      setError(null);
    } catch (err) {
      // Don't show error if request was intentionally aborted
      if (err.name !== 'AbortError') {
        const message = err instanceof Error ? err.message : 'Unknown error occurred';
        if (message.includes('timed out') || err.name === 'AbortError') {
          setError('Request timed out after 30 seconds. Please try again.');
        } else {
          setError(message);
        }
        setComparison(null);
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="fsc-loading">
        <div className="fsc-skeleton">
          <div className="fsc-skeleton-header"></div>
          <div className="fsc-skeleton-content"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fsc-error">
        <h3>Unable to Load Comparison</h3>
        <p>{error}</p>
        <div className="fsc-error-actions">
          <button onClick={fetchComparison} className="fsc-btn-retry">Try Again</button>
          <button onClick={() => window.location.reload()} className="fsc-btn-refresh">Refresh Page</button>
        </div>
        <p className="fsc-error-help">If the problem persists, contact support.</p>
      </div>
    );
  }

  if (!comparison) {
    return <div className="fsc-empty">No comparison data available</div>;
  }

  if (!comparison.comparison) {
    return <div className="fsc-empty">Comparison data incomplete</div>;
  }

  // CRITICAL-5: Safe destructuring with null checks
  const { flash_assessment, slm_assessment, comparison: comp } = comparison || {};
  if (!comp) {
    return <div className="fsc-empty">Invalid comparison data</div>;
  }

  const isConflict = comp.conflict_detected;
  const agreementClass = `fsc-agreement--${comp.agreement_level.toLowerCase()}`;
  const conflictClass = isConflict ? 'fsc-conflict' : 'fsc-agreement';

  // CRITICAL-2: Real escalation handler
  const [escalating, setEscalating] = useState(false);
  const handleEscalation = async () => {
    if (!comp.escalation_to) return;

    setEscalating(true);
    try {
      const response = await apiFetch(`/api/v1/candidates/${candidateId}/escalate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          escalation_to: comp.escalation_to,
          conflict_type: comp.conflict_type,
          reason: comp.escalation_reason,
        }),
      });

      if (!response.ok) {
        throw new Error(`Escalation failed: ${response.status}`);
      }

      alert(`✓ Escalation sent to ${comp.escalation_to.replace(/_/g, ' ').toUpperCase()}`);
    } catch (err) {
      setError(`Failed to escalate: ${err.message}`);
    } finally {
      setEscalating(false);
    }
  };

  return (
    <div className="flash-slm-comparison">
      {/* Header with Agreement Status */}
      <div className={`fsc-header ${agreementClass}`}>
        <div className="fsc-status">
          <div className="fsc-status-badge">{comp.agreement_level}</div>
          {isConflict && <div className="fsc-conflict-badge">{comp.conflict_type}</div>}
        </div>
        <div className="fsc-freshness" title={`Last updated: ${comparison.comparison_generated_at}`}>
          {comparison.data_freshness === 'stale' ? '⚠️ Data Stale (>1hr)' : '✓ Fresh Data'}
        </div>
      </div>

      {/* Conflict Alert (if applicable) */}
      {isConflict && (
        <div className="fsc-conflict-alert">
          <h3>⚠️ Conflict Detected</h3>
          <p>{comp.conflict_reason}</p>
          <div className="fsc-escalation" style={{ marginTop: '12px' }}>
            <strong>Escalation Required:</strong> {comp.escalation_to?.replace(/_/g, ' ').toUpperCase()}
            <p style={{ fontSize: '13px', marginTop: '4px', opacity: 0.85 }}>{comp.escalation_reason}</p>
          </div>
        </div>
      )}

      {/* Two-Column Assessment View */}
      <div className="fsc-assessments">
        {/* Flash Assessment */}
        <div className="fsc-assessment">
          <h2>Flash Interview Assessment</h2>
          {flash_assessment ? (
            <>
              <div className="fsc-recommendation">
                <span className={`fsc-rec-badge rec-${flash_assessment.recommendation.toLowerCase()}`}>
                  {flash_assessment.recommendation}
                </span>
                <span className="fsc-confidence">{flash_assessment.confidence_pct}% confidence</span>
              </div>

              <div className="fsc-scores">
                <ScoreBar label="Technical" value={flash_assessment.technical_score} />
                <ScoreBar label="Communication" value={flash_assessment.communication_score} />
                <ScoreBar label="Problem-Solving" value={flash_assessment.problem_solving_score} />
                <ScoreBar label="Culture Fit" value={flash_assessment.culture_fit_score} />
              </div>

              <div className="fsc-section">
                <h4>Strengths</h4>
                <ul>
                  {flash_assessment.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>

              <div className="fsc-section">
                <h4>Concerns</h4>
                <ul>
                  {flash_assessment.concerns.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>

              <div className="fsc-section">
                <h4>Rationale</h4>
                <p>{flash_assessment.rationale}</p>
              </div>

              <div className="fsc-timestamp">
                {parseISODate(flash_assessment.analyzed_at)?.toLocaleDateString() || 'Unknown date'}
              </div>
            </>
          ) : (
            <div className="fsc-no-data">No interview transcript analyzed yet</div>
          )}
        </div>

        {/* SLM Assessment */}
        <div className="fsc-assessment">
          <h2>SLM Candidate Analysis</h2>
          {slm_assessment ? (
            <>
              <div className="fsc-quality-flags">
                <div className={`fsc-flag flag-${slm_assessment.quality_flag.toLowerCase()}`}>
                  Quality: {slm_assessment.quality_flag}
                </div>
                <div className={`fsc-flag flag-risk-${slm_assessment.risk_level.toLowerCase()}`}>
                  Risk: {slm_assessment.risk_level}
                </div>
              </div>

              <div className="fsc-scores">
                <ScoreBar
                  label="Quality Score"
                  value={Math.round(slm_assessment.quality_score)}
                  max={100}
                />
              </div>

              <div className="fsc-section">
                <h4>Application Pattern</h4>
                <p>
                  <strong>{slm_assessment.application_pattern}</strong>
                  <br />
                  <small>{getPatternDescription(slm_assessment.application_pattern)}</small>
                </p>
              </div>

              {comparison.data_freshness === 'stale' && (
                <div className="fsc-stale-warning">
                  ⚠️ WARNING: SLM data is &gt;1 hour old.{' '}
                  <button onClick={fetchComparison} className="fsc-btn-refresh-inline">Refresh now</button>
                </div>
              )}

              <div className="fsc-metrics">
                <MetricBox
                  label="Applications"
                  value={slm_assessment.total_applications}
                />
                <MetricBox
                  label="Offers"
                  value={slm_assessment.total_offers}
                  secondary={`${slm_assessment.total_hired} hired`}
                />
                <MetricBox
                  label="Success Rate"
                  value={
                    slm_assessment.success_rate !== null && slm_assessment.success_rate !== undefined
                      ? `${(Math.min(1, slm_assessment.success_rate) * 100).toFixed(0)}%`
                      : 'N/A'
                  }
                />
              </div>

              <div className="fsc-timestamp">
                {slm_assessment.is_stale ? '⚠️ ' : '✓ '}
                Last updated: {parseISODate(slm_assessment.last_updated_at)?.toLocaleDateString() || 'Unknown'}
              </div>
            </>
          ) : (
            <div className="fsc-no-data">SLM analysis pending</div>
          )}
        </div>
      </div>

      {/* Comparative Analysis */}
      <div className="fsc-analysis">
        <h2>Comparative Analysis</h2>

        <div className="fsc-score-delta">
          <div className="fsc-label">Score Difference</div>
          <div className={`fsc-delta-value ${comp.score_delta > 0 ? 'positive' : 'negative'}`}>
            {comp.score_delta > 0 ? '+' : ''}{comp.score_delta.toFixed(1)} pts
          </div>
          <p className="fsc-interpretation">{comp.score_interpretation}</p>
        </div>

        <div className="fsc-next-action">
          <h3>Recommended Next Action</h3>
          <div className={`fsc-action-card ${isConflict ? 'escalation' : 'proceed'}`}>
            <p>{comp.next_action}</p>
            {comp.escalation_required && (
              <button
                className="fsc-escalate-btn"
                onClick={handleEscalation}
                disabled={escalating}
                aria-label={`Escalate to ${comp.escalation_to}`}
              >
                {escalating ? 'Escalating...' : `Escalate to ${comp.escalation_to?.replace(/_/g, ' ').toUpperCase()}`}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile-Optimized Footer */}
      <div className="fsc-footer">
        <small>Comparison generated at {parseISODate(comparison.comparison_generated_at)?.toLocaleString() || 'Unknown'}</small>
      </div>
    </div>
  );
};

/**Helper Components*/

/**
 * Renders a horizontal score bar with label and value
 * @param {number} value - Current score
 * @param {string} label - Display label
 * @param {number} max - Maximum value (default 100)
 */
const ScoreBar = ({ label, value, max = 100 }) => {
  // HIGH-8: Clamp value to prevent bar exceeding 100%
  const clampedValue = Math.max(0, Math.min(value, max));
  const percentage = (clampedValue / max) * 100;

  return (
    <div className="fsc-score-bar" role="progressbar" aria-valuenow={clampedValue} aria-valuemin="0" aria-valuemax={max}>
      <div className="fsc-score-label">{label}</div>
      <div className="fsc-score-track">
        <div className="fsc-score-fill" style={{ width: `${percentage}%` }} />
      </div>
      <div className="fsc-score-value">{clampedValue}/{max}</div>
    </div>
  );
};

/**
 * Renders a metric box with value and label
 * @param {string} label - Metric label
 * @param {string|number} value - Metric value
 * @param {string} [secondary] - Secondary text
 */
const MetricBox = ({ label, value, secondary }) => (
  <div className="fsc-metric">
    <div className="fsc-metric-value">{value}</div>
    <div className="fsc-metric-label">{label}</div>
    {secondary && <div className="fsc-metric-secondary">{secondary}</div>}
  </div>
);

// HIGH-10: Centralized pattern descriptions for i18n
const PATTERN_DESCRIPTIONS = {
  STRATEGIC: 'Focused, intentional applications',
  SCATTERED: 'Mixed application approach',
  SPRAY_AND_PRAY: 'High-volume, low-selectivity',
  FOCUSED: 'Very targeted applications',
  REHIRE: 'Returning to previous employer',
};

const getPatternDescription = (pattern) => {
  return PATTERN_DESCRIPTIONS[pattern] || 'Application pattern analysis';
};

// HIGH-12: Prop validation
FlashSLMComparison.propTypes = {
  candidateId: PropTypes.string.isRequired,
  interviewId: PropTypes.string,
};

FlashSLMComparison.defaultProps = {
  interviewId: null,
};

export default FlashSLMComparison;
