/**
 * Admin Weekly Recap Dashboard
 *
 * CEO's executive view: Everything that happened this week at a glance
 *
 * Shows:
 * 1. Weekly Standup Summary (agent execution)
 * 2. HTD Pipeline Progress (SPECIALTY→CORE conversion trend)
 * 3. Opportunity Pipeline (weekly closed, at-risk, stalled)
 * 4. Partner Performance (weekly revenue vs annual pace)
 * 5. Flash Directives (what was told to partners and why)
 * 6. Agent Health (weekly performance metrics)
 * 7. Forecast vs Reality (2030 trajectory update)
 */

import React, { useState, useEffect } from 'react';
import {
  Container, Paper, Tabs, Tab, Box, Grid, Card, CardContent,
  Typography, List, ListItem, ListItemText, Chip, LinearProgress,
  Alert, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Divider, Badge,
} from '@mui/material';
import {
  TrendingUp, TrendingDown, Warning, CheckCircle, Error,
  People, DollarSign, Target, Flame, ArrowUpward, ArrowDownward,
} from '@mui/icons-material';

export default function AdminWeeklyRecapDashboard() {
  const [currentTab, setCurrentTab] = useState(0);
  const [userRole, setUserRole] = useState('ceo'); // 'ceo', 'curtis', 'troy', 'avinash'
  const [weekStart, setWeekStart] = useState(null);
  const [weekEnd, setWeekEnd] = useState(null);
  const [loading, setLoading] = useState(true);

  // Sample data (would come from API)
  const [weeklyData, setWeeklyData] = useState({
    week: 'Aug 4-10, 2026',
    viewing_role: 'ceo', // Determines what sections are visible (praise public, criticize private)
    summary: {
      agents_reporting: 25,
      agents_operational: 23,
      agents_degraded: 2,
      critical_alerts: 1,
      high_alerts: 3,
      partners_on_track: 2,
      partners_behind: 1,
    },
    htd_pipeline: {
      curtis: {
        week_start_core: 8,
        week_end_core: 9,
        in_development: 12,
        passed_gates: 3,
        failed_gates: 1,
        new_core_certified: 1,
        trend: 'positive',
      },
      troy: {
        week_start_core: 15,
        week_end_core: 15,
        in_development: 8,
        passed_gates: 1,
        failed_gates: 0,
        new_core_certified: 0,
        trend: 'flat',
      },
      avinash: {
        week_start_core: 6,
        week_end_core: 7,
        in_development: 5,
        passed_gates: 2,
        failed_gates: 0,
        new_core_certified: 1,
        trend: 'positive',
      },
    },
    opportunities: {
      week_closed: 450000,
      week_closed_count: 1,
      deals_at_risk: 2,
      deals_stalled: 3,
      total_pipeline: 8500000,
      weighted_pipeline: 5200000,
      ytd_closed: 2850000,
      ytd_target: 3200000,
      ytd_pace_pct: 89,
    },
    partner_performance: {
      curtis_core: {
        label: 'Curtis (PRISM CORE)',
        ytd_closed: 950000,
        ytd_target: 4000000,
        ytd_pace_pct: 24,
        week_target: 77000,
        week_closed: 85000,
        week_pace_pct: 110,
        trend: 'accelerating',
        metric: 'CORE clients sourced by Curtis',
      },
      troy_core: {
        label: 'Troy (AXION CORE)',
        ytd_closed: 1200000,
        ytd_target: 3000000,
        ytd_pace_pct: 40,
        week_target: 58000,
        week_closed: 45000,
        week_pace_pct: 78,
        trend: 'behind',
        metric: 'CORE clients sourced by Troy',
      },
      avinash_specialty: {
        label: 'Avinash (BXIN SPECIALTY)',
        ytd_closed: 700000,
        ytd_target: 2000000,
        ytd_pace_pct: 35,
        week_target: 38000,
        week_closed: 55000,
        week_pace_pct: 145,
        trend: 'strong',
        metric: 'SPECIALTY revenue (125% of BXIN cost target)',
      },
    },
    flash_directives: [
      {
        partner: 'Curtis (PRISM Principal)',
        directive: 'ACCELERATE_CORE_DEVELOPMENT',
        reason: 'PRISM CORE clients: Only 45% staffing ready (target 60%). 12 in development, forecast 11 CORE by month 6. Revenue gap: $950K YTD vs $4M target.',
        actions: [
          'PRISM HTD: Hire 3 external CORE this month (PRISM autonomous responsibility)',
          'Accelerate gates for CONTROLLED_OWNERSHIP phase',
          'Increase interview pace from 2/week to 4/week',
          '⚠️ NO cross-BU resource borrowing: PRISM solves PRISM demand independently',
        ],
        status: 'IN_PROGRESS',
        week_issued: 'Aug 4',
      },
      {
        partner: 'Troy (AXION Principal)',
        directive: 'MAINTAIN_CORE_EXCELLENCE',
        reason: 'AXION CORE clients: 75% staffing ready. Strong foundation. Revenue on pace: $1.2M YTD vs $3M target.',
        actions: [
          'AXION: Continue gate progression (1/week passing through CORE_ELIGIBILITY_REVIEW)',
          'Monitor AXION-owned clients for expansion opportunities',
          'Focus on quality: maintain CORE certification standards',
          '⚠️ NO cross-BU resource sharing: AXION owns AXION solutions',
        ],
        status: 'ACTIVE',
        week_issued: 'Aug 4',
      },
      {
        partner: 'Avinash (BXIN Corporate / SPECIALTY)',
        directive: 'SCALE_SPECIALTY_FOR_CORE_PIPELINE',
        reason: 'SPECIALTY monetization: 50% CORE-eligible. Revenue on pace: $700K YTD vs $2M target (125% of BXIN cost goal).',
        actions: [
          'SPECIALTY: Hire 2 external CORE (not quantity, quality)',
          'Monitor SPECIALTY → CORE conversion pipeline for both BUs',
          'NO SPECIALTY scaling until CORE-eligible ratio reaches 55%',
          '⚠️ SPECIALTY supports BOTH BUs independently; revenue belongs to Corporate, not BUs',
        ],
        status: 'IN_PROGRESS',
        week_issued: 'Aug 4',
      },
    ],
    agent_health: {
      recruitment_agent: {
        executions: 47,
        success_rate: 96,
        issues: 1,
        status: 'operational',
      },
      resource_management: {
        executions: 38,
        success_rate: 94,
        issues: 0,
        status: 'operational',
      },
      htd_pipeline: {
        executions: 7,
        success_rate: 100,
        issues: 0,
        status: 'operational',
      },
      flash_orchestration: {
        executions: 7,
        success_rate: 100,
        issues: 0,
        status: 'operational',
      },
      opportunity_tracker: {
        executions: 6,
        success_rate: 100,
        issues: 0,
        status: 'operational',
      },
    },
    forecast_2030: {
      target: 100000000,
      ytd_revenue_pct: 0.85, // YTD toward annual goal
      annual_run_rate: 3400000,
      annual_target: 3500000,
      track_to_2030: {
        current_run_rate: 3400000,
        needed_by_2030: 100000000,
        years_remaining: 3.5,
        required_growth_rate: 28, // % per year
        current_growth_rate: 22,
        gap: 6,
        verdict: 'BEHIND_PACE', // Needs to accelerate 6% annually
      },
    },
  });

  useEffect(() => {
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          📊 Weekly Executive Recap — {weeklyData.week}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Last updated: Friday 5 PM IST
        </Typography>
      </Box>

      <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)} sx={{ mb: 3 }}>
        <Tab label="🏆 Public Wins (All)" />
        <Tab label="📊 HTD Pipeline" />
        <Tab label="💰 Revenue by Line Type" />
        <Tab label="🎯 My Priorities (Private)" />
        <Tab label="⚡ Flash Coordination" />
        <Tab label="🤖 Agent Health" />
        <Tab label="📈 2030 Vision" />
      </Tabs>

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 0: PUBLIC WINS — PRAISE IN PUBLIC ══════════════════════════════ */}
      {/* Philosophy: Celebrate all BUs. Both must stand strong for BlitzenX to grow. */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 0 && (
        <Box>
          <Alert severity="success" sx={{ mb: 3, bgcolor: '#e8f5e9' }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              🏆 WEEK OF SUCCESS — Both AXION and PRISM moving forward. SPECIALTY pipeline strong. BlitzenX on track for $100M by 2030.
            </Typography>
          </Alert>

          <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
            Weekly Celebrations
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            {/* AXION Recognition */}
            <Grid item xs={12} md={6}>
              <Card sx={{ bgcolor: '#f3e5f5', borderLeft: '4px solid #9c27b0' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      ⚡ AXION (Troy)
                    </Typography>
                    <Chip label="STRONG FOUNDATION" color="primary" size="small" />
                  </Box>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    75% CORE certified. Steady momentum on AXION-sourced CORE clients.
                  </Typography>
                  <Typography variant="body2">
                    ✓ Gates progressing smoothly · ✓ CORE client relationships strong · ✓ Quality maintained
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* PRISM Recognition */}
            <Grid item xs={12} md={6}>
              <Card sx={{ bgcolor: '#e3f2fd', borderLeft: '4px solid #2196f3' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      🚀 PRISM (Curtis)
                    </Typography>
                    <Chip label="ACCELERATING" color="success" size="small" />
                  </Box>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    Ramping CORE talent development. PRISM-sourced CORE clients growing.
                  </Typography>
                  <Typography variant="body2">
                    ✓ Development pipeline active · ✓ New CORE gates passing · ✓ Client pipeline expanding
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* SPECIALTY Recognition */}
            <Grid item xs={12} md={6}>
              <Card sx={{ bgcolor: '#fff3e0', borderLeft: '4px solid #ff9800' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      🌍 SPECIALTY (Avinash)
                    </Typography>
                    <Chip label="REVENUE STRONG" color="warning" size="small" />
                  </Box>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    SPECIALTY monetization supporting both BUs' development pipelines.
                  </Typography>
                  <Typography variant="body2">
                    ✓ CORE-eligible capacity growing · ✓ Client utilization up · ✓ Pipeline quality improving
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* Collective Metrics */}
            <Grid item xs={12} md={6}>
              <Card sx={{ bgcolor: '#f5f5f5' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      🎯 BlitzenX Collective
                    </Typography>
                    <Chip label="ON PACE" color="success" size="small" />
                  </Box>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    All agents operational. All BUs executing independently.
                  </Typography>
                  <Typography variant="body2">
                    ✓ 23/25 agents healthy · ✓ $2.85M YTD revenue (89% of annual pace) · ✓ 25 people in HTD pipeline
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Forward Progress */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
              📈 What's Working This Week
            </Typography>
            <List>
              <ListItem>
                <ListItemText
                  primary="CORE Development Momentum"
                  secondary={`Avinash's SPECIALTY pipeline +1 CORE ready, Curtis's PRISM pipeline +1 ready, Troy's AXION pipeline steady. 25 total in development → forecast 23 CORE ready by month 6. Strong velocity across all BUs.`}
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Revenue Execution (LINE TYPE + CLIENT OWNER Model)"
                  secondary={`AXION (Troy's CORE clients): $1.2M YTD / $3M target (40% pace, strong). PRISM (Curtis's CORE clients): $950K YTD / $4M target (accelerating). SPECIALTY (Avinash): $700K YTD / $2M target (strong execution).`}
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="BU Autonomous Operations"
                  secondary={`Each BU solving its own challenges independently. AXION: Stable high performance. PRISM: Strong ramp trajectory. SPECIALTY: Supporting both BUs' pipelines without creating dependency.`}
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="System Health"
                  secondary={`23/25 agents operational. Recruitment: 96% success. HTD Pipeline: 100%. Flash: 100%. All directives enforce BU autonomy and collaborative strength.`}
                />
              </ListItem>
            </List>
          </Paper>

          {/* Role-Based Private Alerts (only visible to affected parties) */}
          {userRole !== 'ceo' && (
            <Paper sx={{ p: 3, mb: 3, bgcolor: '#fff3cd', borderLeft: '4px solid #ff9800' }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', color: '#856404' }}>
                🔒 Private to {userRole === 'curtis' ? 'PRISM' : userRole === 'troy' ? 'AXION' : 'You'}
              </Typography>
              <Alert severity="info">
                <Typography variant="body2">
                  Your priorities and action items are visible only to you and the CEO. This keeps focus on building your BU strong, not on comparison with others.
                </Typography>
              </Alert>
            </Paper>
          )}

          {/* Next Week Opportunities */}
          <Alert severity="success" sx={{ mb: 2, bgcolor: '#e8f5e9' }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
              🚀 NEXT WEEK — ALL BUS BUILDING FORWARD
            </Typography>
            <Typography variant="body2">
              <strong>AXION (Troy):</strong> Continue momentum on gate progression (1/week expected). Build stronger client relationships with sourced CORE clients. · <strong>PRISM (Curtis):</strong> Accelerate CORE pipeline with 3 external hires this month. Strong ramp trajectory building. · <strong>SPECIALTY (Avinash):</strong> Quality-first CORE hiring (2 external). Supporting both BUs' development success. · <strong>Flash:</strong> Daily coordination ensuring each BU's autonomy + shared mission for $100M.
            </Typography>
          </Alert>
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: HTD PIPELINE ═════════════════════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 1 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            SPECIALTY → CORE Conversion Weekly Trend (Each BU Independent)
          </Typography>
          <Alert severity="warning" sx={{ mb: 3 }}>
            <Typography variant="body2">
              <strong>⚠️ BU Autonomous Development:</strong> Each principal (Troy, Curtis, Avinash) owns their own CORE development pipeline and must solve capacity gaps independently. NO cross-BU resource sharing. If PRISM needs CORE faster, PRISM hires/trains. If AXION needs CORE, AXION solves it. SPECIALTY pipeline supports both BUs' needs but doesn't substitute for BU autonomy.
            </Typography>
          </Alert>

          <TableContainer component={Paper}>
            <Table>
              <TableHead sx={{ bgcolor: '#f5f5f5' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Partner</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    CORE Start
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    CORE End
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    +New This Week
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    In Development
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Gates Passed
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Gates Failed
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Trend
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(weeklyData.htd_pipeline).map(([partner, data]) => (
                  <TableRow key={partner}>
                    <TableCell sx={{ fontWeight: 'bold', textTransform: 'capitalize' }}>
                      {partner}
                    </TableCell>
                    <TableCell align="center">{data.week_start_core}</TableCell>
                    <TableCell align="center" sx={{ color: data.new_core_certified > 0 ? '#4caf50' : '#999' }}>
                      {data.week_end_core}
                    </TableCell>
                    <TableCell align="center">
                      {data.new_core_certified > 0 ? (
                        <Chip label={`+${data.new_core_certified}`} color="success" size="small" />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell align="center">{data.in_development}</TableCell>
                    <TableCell align="center" sx={{ color: '#4caf50', fontWeight: 'bold' }}>
                      {data.passed_gates}
                    </TableCell>
                    <TableCell align="center" sx={{ color: data.failed_gates > 0 ? '#d32f2f' : '#999' }}>
                      {data.failed_gates}
                    </TableCell>
                    <TableCell align="center">
                      {data.trend === 'positive' && <TrendingUp sx={{ color: '#4caf50' }} />}
                      {data.trend === 'flat' && <ArrowDownward sx={{ color: '#ff9800' }} />}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Alert severity="info" sx={{ mt: 3 }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
              💡 CORE CONVERSION INSIGHTS
            </Typography>
            <Typography variant="body2">
              • Curtis accelerating: +1 CORE this week, 3 gates passed. Forecast: 11 CORE by month 6.
            </Typography>
            <Typography variant="body2">
              • Troy steady: Strong foundation (75% CORE). Forecasting maintenance of current ratio.
            </Typography>
            <Typography variant="body2">
              • Avinash building: +1 CORE, good progression. 2 gates passed, maintaining quality over quantity.
            </Typography>
          </Alert>
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: REVENUE PIPELINE ═════════════════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 2 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            Sales Pipeline Weekly Performance
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" variant="body2">
                    Week Closed
                  </Typography>
                  <Typography variant="h5" sx={{ mt: 1 }}>
                    ${((weeklyData?.opportunities?.week_closed || 0) / 1000).toFixed(0)}K
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                    {weeklyData.opportunities.week_closed_count} deal(s)
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" variant="body2">
                    Total Pipeline
                  </Typography>
                  <Typography variant="h5" sx={{ mt: 1 }}>
                    ${((weeklyData?.opportunities?.total_pipeline || 0) / 1_000_000).toFixed(1)}M
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                    Weighted: ${((weeklyData?.opportunities?.weighted_pipeline || 0) / 1_000_000).toFixed(1)}M
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ borderLeft: '4px solid #d32f2f' }}>
                <CardContent>
                  <Typography color="textSecondary" variant="body2">
                    At Risk (Closing Soon)
                  </Typography>
                  <Typography variant="h5" sx={{ mt: 1, color: '#d32f2f' }}>
                    {weeklyData.opportunities.deals_at_risk}
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                    Need CORE staffing
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card sx={{ borderLeft: '4px solid #ff9800' }}>
                <CardContent>
                  <Typography color="textSecondary" variant="body2">
                    Stalled (No Activity)
                  </Typography>
                  <Typography variant="h5" sx={{ mt: 1, color: '#ff9800' }}>
                    {weeklyData.opportunities.deals_stalled}
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
                    Restart action needed
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* YTD Progress */}
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              YTD Progress vs Annual Target
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    ${((weeklyData?.opportunities?.ytd_closed || 0) / 1_000_000).toFixed(2)}M / ${((weeklyData?.opportunities?.ytd_target || 0) / 1_000_000).toFixed(1)}M
                  </Typography>
                  <Chip label={`${weeklyData.opportunities.ytd_pace_pct}%`} color="success" size="small" />
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(weeklyData.opportunities.ytd_pace_pct, 100)}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Grid>
            </Grid>
          </Paper>
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: PRIVATE PRIORITIES (CRITICISM IN PRIVATE) ══════════════════ */}
      {/* Only visible to affected BU + CEO. Public section celebrates. Private section improves. */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 3 && (
        <Box>
          <Alert severity="warning" sx={{ mb: 3, bgcolor: '#fff3e0' }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              🔒 PRIVATE SECTION: Visible only to you and Avinash (CEO)
            </Typography>
            <Typography variant="body2">
              This space is for honest feedback and improvement opportunities. Not for broadcast. The philosophy: praise publicly, improve privately. Both BUs strong = BlitzenX strong.
            </Typography>
          </Alert>

          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            Improvement Opportunities This Week
          </Typography>

          {/* PRISM Private Priorities */}
          {(userRole === 'ceo' || userRole === 'curtis') && (
            <Card sx={{ mb: 3, borderLeft: '4px solid #d32f2f' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', color: '#d32f2f' }}>
                  PRISM (Curtis) — Acceleration Opportunities
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="CORE Certification Velocity"
                      secondary="45% CORE ready vs 60% target. Gap: 6 people. Action: Accelerate gate progression on CONTROLLED_OWNERSHIP phase OR begin 3-person external CORE hire this month. PRISM owns the decision."
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Revenue Pace (PRISM CORE Clients)"
                      secondary="$950K YTD vs $4M target (24% pace). Strong month-over-month growth. Continue client sourcing momentum + ensure sufficient CORE capacity for incoming deals."
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          )}

          {/* AXION Private Priorities */}
          {(userRole === 'ceo' || userRole === 'troy') && (
            <Card sx={{ mb: 3, borderLeft: '4px solid #2196f3' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', color: '#2196f3' }}>
                  AXION (Troy) — Maintain Excellence
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Strong Foundation Momentum"
                      secondary="75% CORE certified. Strong gate progression (1/week). Focus: Maintain quality standards, deepen CORE client relationships, identify expansion opportunities with existing clients."
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Revenue Pace (AXION CORE Clients)"
                      secondary="$1.2M YTD vs $3M target (40% pace). Solid trajectory. Opportunity: Identify 1-2 key client expansion deals this quarter."
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          )}

          {/* SPECIALTY Private Priorities */}
          {(userRole === 'ceo' || userRole === 'avinash') && (
            <Card sx={{ mb: 3, borderLeft: '4px solid #ff9800' }}>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold', color: '#ff9800' }}>
                  SPECIALTY (Avinash) — Pipeline Quality
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="CORE-Eligible Growth"
                      secondary="50% CORE-eligible. Target: 55% by month 3. Quality-first: Ensure gate rigor maintained. 2 external CORE hires this month to support both BUs' pipelines."
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="SPECIALTY Revenue Execution"
                      secondary="$700K YTD vs $2M target (35% pace). On track. Ensure utilization stays high, no bench waste, CORE-eligible pipeline keeps feeding both BUs."
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          )}
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 4: FLASH DIRECTIVES ═════════════════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 4 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            Flash Daily Directives (What Flash Told Partners to Do)
          </Typography>

          {weeklyData.flash_directives.map((directive, idx) => (
            <Card key={idx} sx={{ mb: 2, borderLeft: `4px solid ${directive.status === 'IN_PROGRESS' ? '#ff9800' : '#4caf50'}` }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      {directive.partner}
                    </Typography>
                    <Typography variant="body2" color="textSecondary" sx={{ mt: 0.5 }}>
                      {directive.directive.replace(/_/g, ' ')}
                    </Typography>
                  </Box>
                  <Chip
                    label={directive.status}
                    size="small"
                    color={directive.status === 'IN_PROGRESS' ? 'warning' : 'success'}
                  />
                </Box>

                <Alert severity="info" sx={{ mb: 2 }}>
                  <Typography variant="body2">{directive.reason}</Typography>
                </Alert>

                <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                  Action Items:
                </Typography>
                <List dense>
                  {directive.actions.map((action, i) => (
                    <ListItem key={i} sx={{ py: 0.5 }}>
                      <ListItemText
                        primary={action}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          ))}

          <Alert severity="success" sx={{ mt: 3 }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
              ✓ FLASH COORDINATION COMPLETE
            </Typography>
            <Typography variant="body2">
              3 directives issued (1 critical, 2 strategic). All partners briefed before CEO call on Thursday morning.
            </Typography>
          </Alert>
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 6: AGENT HEALTH ══════════════════════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 5 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            Agent Performance This Week
          </Typography>

          <TableContainer component={Paper}>
            <Table>
              <TableHead sx={{ bgcolor: '#f5f5f5' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>Agent</TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Executions
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Success Rate
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Issues
                  </TableCell>
                  <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                    Status
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(weeklyData.agent_health).map(([agent, health]) => (
                  <TableRow key={agent}>
                    <TableCell sx={{ fontWeight: '500', textTransform: 'capitalize' }}>
                      {agent.replace(/_/g, ' ')}
                    </TableCell>
                    <TableCell align="center">{health.executions}</TableCell>
                    <TableCell align="center">
                      <Chip label={`${health.success_rate}%`} size="small" color={health.success_rate >= 95 ? 'success' : 'warning'} />
                    </TableCell>
                    <TableCell align="center">
                      {health.issues > 0 ? (
                        <Chip label={health.issues} size="small" color="error" />
                      ) : (
                        '✓'
                      )}
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={health.status.toUpperCase()}
                        size="small"
                        color={health.status === 'operational' ? 'success' : 'warning'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ════════════════════════════════════════════════════════════════════ */}
      {/* TAB 7: 2030 FORECAST ═════════════════════════════════════════════════ */}
      {/* ════════════════════════════════════════════════════════════════════ */}
      {currentTab === 6 && (
        <Box>
          <Typography variant="h6" sx={{ mb: 3, fontWeight: 'bold' }}>
            2030 Revenue Target Trajectory
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 3, bgcolor: '#f0f7ff' }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  🎯 Target
                </Typography>
                <Typography variant="h3" sx={{ color: '#1976d2', fontWeight: 'bold', mb: 1 }}>
                  ${((weeklyData?.forecast_2030?.target || 0) / 1_000_000).toFixed(0)}M
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Required by March 31, 2030
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 3, bgcolor: '#f5f5f5' }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  📈 Current Run Rate
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 'bold', mb: 1 }}>
                  ${((weeklyData?.forecast_2030?.annual_run_rate || 0) / 1_000_000).toFixed(1)}M/year
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Based on YTD performance
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Trajectory Analysis
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="textSecondary">
                  Current Annual Target
                </Typography>
                <Typography variant="h6" sx={{ mt: 0.5 }}>
                  ${((weeklyData?.forecast_2030?.annual_target || 0) / 1_000_000).toFixed(1)}M
                </Typography>
              </Grid>

              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="textSecondary">
                  YTD vs Target
                </Typography>
                <Typography variant="h6" sx={{ mt: 0.5 }}>
                  {Math.round(weeklyData.forecast_2030.ytd_revenue_pct * 100)}% of annual pace
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
              </Grid>

              <Grid item xs={12}>
                <Alert severity={weeklyData.forecast_2030.track_to_2030.verdict === 'ON_TRACK' ? 'success' : 'warning'}>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    🚀 2030 FORECAST: {weeklyData.forecast_2030.track_to_2030.verdict}
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Current growth rate: {weeklyData.forecast_2030.track_to_2030.current_growth_rate}% annually
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Required growth rate: {weeklyData.forecast_2030.track_to_2030.required_growth_rate}% annually
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#d32f2f' }}>
                    ⚠️ SHORTFALL: Need to accelerate by {weeklyData.forecast_2030.track_to_2030.gap}% annually to hit $100M by 2030
                  </Typography>
                </Alert>
              </Grid>

              <Grid item xs={12}>
                <Typography variant="body2" sx={{ mt: 2, fontStyle: 'italic' }}>
                  Recommendation: Scale CORE team aggressively. Current growth (22%) insufficient for $100M target. Need 28% annual growth = focus on HTD hiring + CORE certification acceleration.
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Box>
      )}
    </Container>
  );
}
