/**
 * Admin Daily Flash Dashboard
 *
 * CEO's daily command center: Agent standup + HTD pipeline + Opportunity tracking + Partner success
 *
 * Shows:
 * 1. Daily Agent Standup (agents report performance yesterday)
 * 2. HTD Pipeline Health (SPECIALTY→CORE conversion by partner)
 * 3. Opportunity Pipeline (sales deals, stalled deals, at-risk deals)
 * 4. Partner Success Track (weekly revenue pace, action items)
 * 5. Flash Command Center (CEO directives to agents)
 */

import React, { useState, useEffect } from 'react';
import {
  Container, Paper, Tabs, Tab, Box, Grid, Card, CardContent,
  Typography, List, ListItem, ListItemText, Chip, LinearProgress,
  Alert, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, CircularProgress,
} from '@mui/material';
import {
  TrendingUp, TrendingDown, Warning, CheckCircle, Error,
  People, TrendingUpward, MoreVert,
} from '@mui/icons-material';
import { apiCall } from '../services/api';

export default function AdminDailyFlashDashboard() {
  const [currentTab, setCurrentTab] = useState(0);
  const [loading, setLoading] = useState(true);

  // Data states
  const [standupData, setStandupData] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [opportunityData, setOpportunityData] = useState(null);
  const [htdHealthData, setHtdHealthData] = useState(null);

  // CEO feedback dialog
  const [feedbackDialog, setFeedbackDialog] = useState({
    open: false,
    agentName: '',
    feedback: '',
  });

  useEffect(() => {
    loadDashboardData();
    // Refresh every 60 seconds
    const interval = setInterval(loadDashboardData, 60000);
    return () => clearInterval(interval);
  }, []);

  async function loadDashboardData() {
    try {
      setLoading(true);

      // Load all 4 data streams in parallel
      const [standup, pipeline, opportunity, htdHealth] = await Promise.all([
        apiCall('GET', '/admin/agents/standup').catch(() => null),
        apiCall('GET', '/htd/partners/conversion-health').catch(() => null),
        apiCall('GET', '/opportunities/pipeline-health').catch(() => null),
        apiCall('GET', '/admin/agents/fear').catch(() => null),
      ]);

      setStandupData(standup?.data || {});
      setPipelineData(pipeline?.data || {});
      setOpportunityData(opportunity?.data || {});
      setHtdHealthData(htdHealth?.data || {});
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  }

  const handleFeedback = async () => {
    if (!feedbackDialog.feedback.trim()) return;

    try {
      await apiCall('POST', '/admin/agents/feedback', {
        agent_name: feedbackDialog.agentName,
        feedback: feedbackDialog.feedback,
        feedback_type: 'ceo_directive',
      });

      setFeedbackDialog({ open: false, agentName: '', feedback: '' });
      loadDashboardData();
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 'bold' }}>
        ⚡ Flash Command Center — Daily Standup
      </Typography>

      <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)} sx={{ mb: 3, borderBottom: '1px solid #ddd' }}>
        <Tab label="Daily Standup" />
        <Tab label="HTD Pipeline" />
        <Tab label="Opportunities" />
        <Tab label="Partner Tracking" />
        <Tab label="Agent Health" />
      </Tabs>

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: DAILY STANDUP — Agent Reports ════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 0 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Agent Daily Reports (Yesterday's Performance)
          </Typography>

          {standupData?.agent_reports ? (
            <Grid container spacing={2}>
              {standupData.agent_reports.map((agent, idx) => (
                <Grid item xs={12} md={6} key={idx}>
                  <Card sx={{ borderLeft: `4px solid ${agent.status === 'operational' ? '#4caf50' : '#ff9800'}` }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="h6">{agent.agent_name}</Typography>
                        <Chip
                          label={agent.status.toUpperCase()}
                          size="small"
                          color={agent.status === 'operational' ? 'success' : 'warning'}
                          variant="outlined"
                        />
                      </Box>

                      <Grid container spacing={1} sx={{ mb: 2 }}>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            Executions
                          </Typography>
                          <Typography variant="h6">{agent.execution_count || 0}</Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            Success Rate
                          </Typography>
                          <Typography variant="h6">{agent.success_rate || 0}%</Typography>
                        </Grid>
                      </Grid>

                      <Box sx={{ mb: 2 }}>
                        <LinearProgress
                          variant="determinate"
                          value={agent.success_rate || 0}
                          sx={{ height: 6, borderRadius: 3 }}
                        />
                      </Box>

                      {agent.issues && agent.issues.length > 0 && (
                        <Alert severity="warning" sx={{ mb: 2 }}>
                          <Typography variant="body2">
                            {agent.issues.length} issue(s) flagged. CEO review requested.
                          </Typography>
                        </Alert>
                      )}

                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => setFeedbackDialog({ open: true, agentName: agent.agent_name, feedback: '' })}
                      >
                        Provide Feedback
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Alert severity="info">No agent reports yet. Run standup job (8:00 AM EST).</Alert>
          )}

          {standupData?.validation_issues && standupData.validation_issues.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" sx={{ mb: 2, color: '#d32f2f' }}>
                ⚠️ Validation Issues ({standupData.validation_issues.length})
              </Typography>
              <List>
                {standupData.validation_issues.map((issue, idx) => (
                  <ListItem key={idx} sx={{ bgcolor: '#fff3e0', borderLeft: '3px solid #ff9800', mb: 1 }}>
                    <ListItemText
                      primary={issue.agent_name}
                      secondary={`${issue.issue_type}: ${issue.details}`}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: HTD PIPELINE — SPECIALTY→CORE Conversion ═════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 1 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            SPECIALTY → CORE Pipeline Health (Development Forecast)
          </Typography>

          {htdHealthData?.bu_breakdown ? (
            <Grid container spacing={2}>
              {htdHealthData.bu_breakdown.map((bu, idx) => {
                const healthColor = bu.core_pct >= 60 ? '#4caf50' : bu.core_pct >= 40 ? '#ff9800' : '#d32f2f';
                return (
                  <Grid item xs={12} md={6} key={idx}>
                    <Card sx={{ borderLeft: `4px solid ${healthColor}` }}>
                      <CardContent>
                        <Typography variant="h6" sx={{ mb: 2 }}>
                          {bu.bu_name}
                        </Typography>

                        <Grid container spacing={2} sx={{ mb: 2 }}>
                          <Grid item xs={6}>
                            <Typography variant="body2" color="textSecondary">
                              Total People
                            </Typography>
                            <Typography variant="h6">{bu.total_headcount}</Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography variant="body2" color="textSecondary">
                              CORE Certified
                            </Typography>
                            <Typography variant="h6" sx={{ color: healthColor }}>
                              {bu.core_certified} ({bu.core_pct}%)
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography variant="body2" color="textSecondary">
                              In Development
                            </Typography>
                            <Typography variant="h6">{bu.in_development}</Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography variant="body2" color="textSecondary">
                              Target: 60%
                            </Typography>
                            <Typography variant="h6">Gap: {Math.max(0, Math.ceil(bu.total_headcount * 0.6 - bu.core_certified))}</Typography>
                          </Grid>
                        </Grid>

                        <Box sx={{ mb: 2 }}>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(bu.core_pct, 100)}
                            sx={{ height: 8, borderRadius: 4 }}
                          />
                        </Box>

                        {bu.htd_needed && (
                          <Alert severity="error" sx={{ mb: 2 }}>
                            <Typography variant="body2">
                              🚨 HTD ALERT: No one in development pipeline. Hire external CORE now.
                            </Typography>
                          </Alert>
                        )}

                        {bu.core_pct >= 60 && bu.in_development > 0 && (
                          <Alert severity="success" sx={{ mb: 2 }}>
                            <Typography variant="body2">
                              ✓ On track. {bu.in_development} in pipeline developing to CORE.
                            </Typography>
                          </Alert>
                        )}

                        {bu.core_pct < 60 && bu.core_pct > 0 && bu.in_development > 0 && (
                          <Alert severity="warning" sx={{ mb: 2 }}>
                            <Typography variant="body2">
                              ⚠️ Behind target. Accelerate HTD development or hire external.
                            </Typography>
                          </Alert>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          ) : (
            <Alert severity="info">Loading HTD pipeline data...</Alert>
          )}
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: OPPORTUNITIES — Sales Pipeline ════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 2 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Sales Opportunities → $100M Target
          </Typography>

          {opportunityData?.pipeline_health ? (
            <>
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                    <Typography color="textSecondary" variant="body2">
                      Total Pipeline
                    </Typography>
                    <Typography variant="h5" sx={{ mt: 1 }}>
                      ${(opportunityData.total_pipeline_usd / 1_000_000).toFixed(1)}M
                    </Typography>
                  </Paper>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#e8f5e9' }}>
                    <Typography color="textSecondary" variant="body2">
                      Probability-Weighted
                    </Typography>
                    <Typography variant="h5" sx={{ mt: 1 }}>
                      ${(opportunityData.weighted_pipeline_usd / 1_000_000).toFixed(1)}M
                    </Typography>
                  </Paper>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#fff3e0' }}>
                    <Typography color="textSecondary" variant="body2">
                      Stalled Deals
                    </Typography>
                    <Typography variant="h5" sx={{ mt: 1 }}>
                      {opportunityData.stalled_count || 0}
                    </Typography>
                  </Paper>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f3e5f5' }}>
                    <Typography color="textSecondary" variant="body2">
                      At-Risk (Closing Soon)
                    </Typography>
                    <Typography variant="h5" sx={{ mt: 1 }}>
                      {opportunityData.at_risk_count || 0}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              {opportunityData.stalled_deals && opportunityData.stalled_deals.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2, color: '#d32f2f' }}>
                    ⚠️ Stalled Deals Requiring Restart
                  </Typography>
                  <List>
                    {opportunityData.stalled_deals.map((deal, idx) => (
                      <ListItem key={idx} sx={{ bgcolor: '#fff3e0', mb: 1, borderRadius: 1 }}>
                        <ListItemText
                          primary={`${deal.client_name} - $${deal.deal_size_usd.toLocaleString()}`}
                          secondary={`Stage: ${deal.stage} | No activity: ${deal.days_stalled} days`}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </>
          ) : (
            <Alert severity="info">Loading opportunity data...</Alert>
          )}
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 4: PARTNER TRACKING — Weekly Revenue Pace ══════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 3 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Partner Weekly Tracking (Before Thursday CEO Call)
          </Typography>

          <Alert severity="info" sx={{ mb: 3 }}>
            Click "View Details" for each partner to see their action items and coaching before CEO call.
          </Alert>

          {pipelineData?.bu_breakdown ? (
            <Grid container spacing={2}>
              {pipelineData.bu_breakdown.map((partner, idx) => (
                <Grid item xs={12} md={6} key={idx}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" sx={{ mb: 2 }}>
                        {partner.bu_name || `Partner ${idx + 1}`}
                      </Typography>

                      <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            Target (Annual)
                          </Typography>
                          <Typography variant="h6">
                            $
                            {partner.annual_target_usd
                              ? (partner.annual_target_usd / 1_000_000).toFixed(1)
                              : '?'}
                            M
                          </Typography>
                        </Grid>

                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            YTD Progress
                          </Typography>
                          <Typography variant="h6">{partner.ytd_pace_pct || 0}%</Typography>
                        </Grid>
                      </Grid>

                      <Box sx={{ mb: 2 }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(partner.ytd_pace_pct || 0, 100)}
                          sx={{ height: 8, borderRadius: 4 }}
                          color={partner.ytd_pace_pct >= 85 ? 'success' : partner.ytd_pace_pct >= 70 ? 'warning' : 'error'}
                        />
                      </Box>

                      <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                        {partner.ytd_pace_pct >= 100
                          ? '🔥 Crushing pace! Keep it up.'
                          : partner.ytd_pace_pct >= 85
                          ? '📈 On track. Stay focused.'
                          : partner.ytd_pace_pct >= 70
                          ? '⚠️ Slightly behind. Action items ready.'
                          : '🚨 BEHIND PACE. Urgent coaching needed.'}
                      </Typography>

                      <Button size="small" variant="outlined">
                        View Details
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Alert severity="info">Loading partner tracking data...</Alert>
          )}
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 5: AGENT HEALTH — Fear/State Dashboard ══════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 4 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Agent Excellence Metrics (Maturity + State Tracking)
          </Typography>

          <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
            These agents are tracked for operational excellence:
          </Typography>

          {htdHealthData?.agents ? (
            <Grid container spacing={2}>
              {htdHealthData.agents.map((agent, idx) => (
                <Grid item xs={12} md={6} key={idx}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="h6">{agent.name}</Typography>
                        <Chip label={agent.tier} size="small" />
                      </Box>

                      <Grid container spacing={1} sx={{ mb: 2 }}>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            Maturity
                          </Typography>
                          <Typography variant="h6">{agent.maturity_score || 0}/100</Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="body2" color="textSecondary">
                            Success Rate
                          </Typography>
                          <Typography variant="h6">{agent.success_rate || 0}%</Typography>
                        </Grid>
                      </Grid>

                      <Box sx={{ mb: 2 }}>
                        <LinearProgress variant="determinate" value={agent.maturity_score || 0} />
                      </Box>

                      <Typography variant="caption" color="textSecondary">
                        Last execution: {agent.last_execution ? new Date(agent.last_execution).toLocaleString() : 'Never'}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Alert severity="info">Loading agent health data...</Alert>
          )}
        </Box>
      )}

      {/* CEO FEEDBACK DIALOG */}
      <Dialog open={feedbackDialog.open} onClose={() => setFeedbackDialog({ ...feedbackDialog, open: false })} maxWidth="sm" fullWidth>
        <DialogTitle>Provide Feedback to {feedbackDialog.agentName}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={4}
            placeholder="Enter feedback, coaching, or directive..."
            value={feedbackDialog.feedback}
            onChange={(e) => setFeedbackDialog({ ...feedbackDialog, feedback: e.target.value })}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFeedbackDialog({ ...feedbackDialog, open: false })}>Cancel</Button>
          <Button onClick={handleFeedback} variant="contained">
            Submit Feedback
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
