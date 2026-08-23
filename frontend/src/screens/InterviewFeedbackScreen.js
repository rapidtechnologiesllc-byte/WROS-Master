import React, { useState, useEffect } from 'react';
import { Card, Button, Input, TextArea, Select, Badge } from '../components/ui';
import { apiRequest } from '../services/api/client';
import './InterviewFeedbackScreen.css';

export default function InterviewFeedbackScreen({ interviewId, candidateName }) {
  const [panelFeedback, setPanelFeedback] = useState([]);
  const [flashAnalysis, setFlashAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPanelMember, setSelectedPanelMember] = useState(null);
  const [coachingEmail, setCoachingEmail] = useState('');
  const [showCoachingModal, setShowCoachingModal] = useState(false);

  useEffect(() => {
    loadFeedbackData();
  }, [interviewId]);

  const loadFeedbackData = async () => {
    try {
      setLoading(true);

      // Get panel feedback
      const panelRes = await apiRequest(`/interviews/${interviewId}/feedback`, 'GET');
      setPanelFeedback(panelRes.data || []);

      // Get Flash analysis
      const flashRes = await apiRequest(`/flash/interviews/${interviewId}/analysis`, 'GET');
      setFlashAnalysis(flashRes.data || null);

      setError('');
    } catch (err) {
      setError(`Failed to load feedback: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getScoreDifference = (panelScore, flashScore) => {
    if (!panelScore || !flashScore) return 0;
    return flashScore - panelScore;
  };

  const getAgreementColor = (difference) => {
    if (Math.abs(difference) <= 10) return '#0ca30c'; // Green - Agree
    if (Math.abs(difference) <= 20) return '#eda100'; // Yellow - Slight disagreement
    return '#ec835a'; // Orange/Red - Strong disagreement
  };

  const getDifferenceLabel = (difference) => {
    if (difference === 0) return 'Perfect Match';
    if (difference > 0) return `Flash +${difference}`;
    return `Flash ${difference}`;
  };

  const sendCoachingEmail = async (panelMember) => {
    if (!coachingEmail.trim()) {
      alert('Please write your coaching feedback');
      return;
    }

    try {
      await apiRequest(`/interviews/${interviewId}/coaching-email`, 'POST', {
        panel_member_id: panelMember.id,
        panel_member_email: panelMember.email,
        flash_analysis: flashAnalysis,
        coaching_message: coachingEmail,
        candidate_name: candidateName,
      });

      alert(`Coaching email sent to ${panelMember.name}`);
      setShowCoachingModal(false);
      setCoachingEmail('');
      setSelectedPanelMember(null);
    } catch (err) {
      alert(`Failed to send email: ${err.message}`);
    }
  };

  if (loading) return <div className="loading">Loading interview feedback...</div>;

  return (
    <div className="interview-feedback-container">
      <div className="header">
        <h1>Interview Feedback & Analysis</h1>
        <p className="subtitle">{candidateName} | Interview ID: {interviewId}</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* FLASH ANALYSIS CARD */}
      {flashAnalysis && (
        <Card className="flash-analysis-card">
          <div className="flash-header">
            <h2>Flash AI Analysis</h2>
            <Badge
              color={flashAnalysis.recommendation === 'HIRE' ? '#0ca30c' : flashAnalysis.recommendation === 'NO_HIRE' ? '#ec835a' : '#eda100'}
              text={`${flashAnalysis.recommendation} - ${flashAnalysis.confidence_pct}% Confidence`}
            />
          </div>

          <div className="flash-scores">
            <div className="score-box">
              <span className="score-label">Technical</span>
              <span className="score-value">{flashAnalysis.technical_score}/100</span>
            </div>
            <div className="score-box">
              <span className="score-label">Communication</span>
              <span className="score-value">{flashAnalysis.communication_score}/100</span>
            </div>
            <div className="score-box">
              <span className="score-label">Problem-Solving</span>
              <span className="score-value">{flashAnalysis.problem_solving_score}/100</span>
            </div>
            <div className="score-box">
              <span className="score-label">Culture Fit</span>
              <span className="score-value">{flashAnalysis.culture_fit_score}/100</span>
            </div>
          </div>

          <div className="flash-rationale">
            <p><strong>Reasoning:</strong> {flashAnalysis.rationale}</p>
          </div>

          <div className="flash-details">
            <div className="strengths">
              <h4>Strengths</h4>
              <ul>
                {flashAnalysis.strengths?.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
            <div className="concerns">
              <h4>Concerns</h4>
              <ul>
                {flashAnalysis.concerns?.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flash-next-steps">
            <p><strong>Next Steps:</strong> {flashAnalysis.next_steps}</p>
          </div>
        </Card>
      )}

      {/* PANEL FEEDBACK vs FLASH COMPARISON */}
      <div className="comparison-section">
        <h2>Panel Feedback vs Flash Analysis</h2>

        {panelFeedback.length === 0 ? (
          <div className="no-feedback">No panel feedback submitted yet</div>
        ) : (
          panelFeedback.map((member, index) => {
            const techDiff = getScoreDifference(member.technical_score, flashAnalysis?.technical_score);
            const commDiff = getScoreDifference(member.communication_score, flashAnalysis?.communication_score);
            const probDiff = getScoreDifference(member.problem_solving_score, flashAnalysis?.problem_solving_score);
            const cultureDiff = getScoreDifference(member.culture_fit_score, flashAnalysis?.culture_fit_score);

            return (
              <Card key={index} className="panel-comparison-card">
                <div className="panel-header">
                  <h3>{member.name} <span className="role">({member.role})</span></h3>
                  <Button
                    onClick={() => {
                      setSelectedPanelMember(member);
                      setShowCoachingModal(true);
                    }}
                    className="coaching-btn"
                  >
                    Send Coaching Email
                  </Button>
                </div>

                <div className="scores-grid">
                  <div className="score-comparison">
                    <div className="dimension">Technical</div>
                    <div className="panel-score">{member.technical_score || '-'}/5</div>
                    <div className="flash-score">{flashAnalysis?.technical_score ? Math.round(flashAnalysis.technical_score / 20) : '-'}/5</div>
                    <div
                      className="agreement-indicator"
                      style={{
                        backgroundColor: getAgreementColor(techDiff),
                        color: 'white'
                      }}
                    >
                      {getDifferenceLabel(techDiff)}
                    </div>
                  </div>

                  <div className="score-comparison">
                    <div className="dimension">Communication</div>
                    <div className="panel-score">{member.communication_score || '-'}/5</div>
                    <div className="flash-score">{flashAnalysis?.communication_score ? Math.round(flashAnalysis.communication_score / 20) : '-'}/5</div>
                    <div
                      className="agreement-indicator"
                      style={{
                        backgroundColor: getAgreementColor(commDiff),
                        color: 'white'
                      }}
                    >
                      {getDifferenceLabel(commDiff)}
                    </div>
                  </div>

                  <div className="score-comparison">
                    <div className="dimension">Problem-Solving</div>
                    <div className="panel-score">{member.problem_solving_score || '-'}/5</div>
                    <div className="flash-score">{flashAnalysis?.problem_solving_score ? Math.round(flashAnalysis.problem_solving_score / 20) : '-'}/5</div>
                    <div
                      className="agreement-indicator"
                      style={{
                        backgroundColor: getAgreementColor(probDiff),
                        color: 'white'
                      }}
                    >
                      {getDifferenceLabel(probDiff)}
                    </div>
                  </div>

                  <div className="score-comparison">
                    <div className="dimension">Culture Fit</div>
                    <div className="panel-score">{member.culture_fit_score || '-'}/5</div>
                    <div className="flash-score">{flashAnalysis?.culture_fit_score ? Math.round(flashAnalysis.culture_fit_score / 20) : '-'}/5</div>
                    <div
                      className="agreement-indicator"
                      style={{
                        backgroundColor: getAgreementColor(cultureDiff),
                        color: 'white'
                      }}
                    >
                      {getDifferenceLabel(cultureDiff)}
                    </div>
                  </div>
                </div>

                <div className="panel-comments">
                  <h4>Panel Member Comments</h4>
                  <p>{member.comments || 'No comments provided'}</p>
                </div>

                <div className="agreement-summary">
                  {Math.abs(techDiff) <= 10 && Math.abs(commDiff) <= 10 && Math.abs(probDiff) <= 10 && Math.abs(cultureDiff) <= 10 ? (
                    <p style={{ color: '#0ca30c' }}>✓ Panel and Flash largely agree on this candidate</p>
                  ) : (
                    <p style={{ color: '#eda100' }}>⚠ Panel and Flash have some disagreement - review before final decision</p>
                  )}
                </div>
              </Card>
            );
          })
        )}
      </div>

      {/* HIRING MANAGER DECISION */}
      <Card className="decision-card">
        <h2>Hiring Manager Decision</h2>
        <div className="decision-guide">
          <p><strong>Recommendation:</strong> {flashAnalysis?.recommendation}</p>
          <p><strong>Confidence:</strong> {flashAnalysis?.confidence_pct}%</p>
          <p><strong>Next Steps:</strong> {flashAnalysis?.next_steps}</p>
          <p className="decision-note">
            Based on Flash's analysis of the interview transcript plus panel feedback above,
            make your hiring decision. When there's disagreement between Flash and panel members,
            consider whether Flash detected something the panel missed (via transcript analysis)
            or whether the panel has context Flash doesn't have.
          </p>
        </div>
        <Button className="primary-btn">Approve Hire</Button>
        <Button className="secondary-btn">Request Additional Info</Button>
        <Button className="reject-btn">Reject</Button>
      </Card>

      {/* COACHING EMAIL MODAL */}
      {showCoachingModal && selectedPanelMember && (
        <div className="modal-overlay" onClick={() => setShowCoachingModal(false)}>
          <Card className="coaching-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Send Coaching Email to {selectedPanelMember.name}</h2>
            <p className="modal-description">
              Share your feedback on their assessment. Flash's perspective vs their scoring may
              highlight where additional context or interview training could help.
            </p>

            <div className="flash-context">
              <h4>Flash's Assessment (for reference)</h4>
              <p>Technical: {flashAnalysis?.technical_score} | Communication: {flashAnalysis?.communication_score}</p>
              <p>Reasoning: {flashAnalysis?.rationale}</p>
            </div>

            <TextArea
              value={coachingEmail}
              onChange={(e) => setCoachingEmail(e.target.value)}
              placeholder={`Example:\n\nHi ${selectedPanelMember.name},\n\nThanks for your feedback on ${candidateName}. Flash's transcript analysis suggests the candidate's technical depth is stronger than reflected in your scoring. Consider reviewing the interview transcript focusing on their problem-solving approach...\n\nKey areas to watch in future interviews:`}
              rows={8}
            />

            <div className="modal-actions">
              <Button
                className="send-btn"
                onClick={() => sendCoachingEmail(selectedPanelMember)}
              >
                Send Coaching Email
              </Button>
              <Button
                className="cancel-btn"
                onClick={() => setShowCoachingModal(false)}
              >
                Cancel
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
