/**Phase 3: Flash vs SLM Comparison Component
 *
 * Displays Flash interview assessment vs SLM candidate metrics side-by-side.
 * Shows conflicts, agreement level, and next-action recommendations.
 * Responsive design for mobile/tablet/desktop.
 */

import React, { useState, useEffect } from 'react';
import './FlashSLMComparison.css';

const FlashSLMComparison = ({ candidateId, interviewId }) => {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSection, setExpandedSection] = useState('overview');

  useEffect(() => {
    fetchComparison();
  }, [candidateId, interviewId]);

  const fetchComparison = async () => {
    try {
      setLoading(true);
      const url = `/api/v1/candidates/${candidateId}/flash-slm-comparison${interviewId ? `?interview_id=${interviewId}` : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      setComparison(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setComparison(null);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="fsc-loading">Loading comparison...</div>;
  }

  if (error) {
    return <div className="fsc-error">Error: {error}</div>;
  }

  if (!comparison) {
    return <div className="fsc-empty">No comparison data available</div>;
  }

  const { flash_assessment, slm_assessment, comparison: comp } = comparison;
  const isConflict = comp.conflict_detected;
  const agreementClass = `fsc-agreement--${comp.agreement_level.toLowerCase()}`;
  const conflictClass = isConflict ? 'fsc-conflict' : 'fsc-agreement';

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
                {new Date(flash_assessment.analyzed_at).toLocaleDateString()}
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
                    slm_assessment.success_rate
                      ? `${(slm_assessment.success_rate * 100).toFixed(0)}%`
                      : 'N/A'
                  }
                />
              </div>

              <div className="fsc-timestamp">
                {slm_assessment.is_stale ? '⚠️ ' : '✓ '}
                Last updated: {new Date(slm_assessment.last_updated_at).toLocaleDateString()}
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
              <button className="fsc-escalate-btn" onClick={() => alert('Escalation would be triggered here')}>
                Escalate to {comp.escalation_to?.replace(/_/g, ' ').toUpperCase()}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile-Optimized Footer */}
      <div className="fsc-footer">
        <small>Comparison generated at {new Date(comparison.comparison_generated_at).toLocaleString()}</small>
      </div>
    </div>
  );
};

/**Helper Components*/

const ScoreBar = ({ label, value, max = 100 }) => (
  <div className="fsc-score-bar">
    <div className="fsc-score-label">{label}</div>
    <div className="fsc-score-track">
      <div className="fsc-score-fill" style={{ width: `${(value / max) * 100}%` }} />
    </div>
    <div className="fsc-score-value">{value}</div>
  </div>
);

const MetricBox = ({ label, value, secondary }) => (
  <div className="fsc-metric">
    <div className="fsc-metric-value">{value}</div>
    <div className="fsc-metric-label">{label}</div>
    {secondary && <div className="fsc-metric-secondary">{secondary}</div>}
  </div>
);

const getPatternDescription = (pattern) => {
  const descriptions = {
    STRATEGIC: 'Focused, intentional applications',
    SCATTERED: 'Mixed application approach',
    SPRAY_AND_PRAY: 'High-volume, low-selectivity',
    FOCUSED: 'Very targeted applications',
    REHIRE: 'Returning to previous employer',
  };
  return descriptions[pattern] || 'Application pattern analysis';
};

export default FlashSLMComparison;
