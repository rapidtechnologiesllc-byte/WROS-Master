import React, { useState, useEffect } from 'react';
import {
  Container,
  TabList,
  Tab,
  Panel,
  Card,
  Button,
  Spinner,
  MessageBox,
  Icon,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@carbon/react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './LearningAnalyticsDashboard.scss';

/**
 * Learning Analytics Dashboard - Phase 4
 *
 * Visualizes autonomous learning system in action:
 * 1. Genetic Populations: Generation history, fitness distribution, elite chromosomes
 * 2. A/B Tests: Stage progression, Thompson allocation, formation health
 * 3. Behavioral Rules: Rule execution history, cascade effects
 * 4. Cascading Signals: Inter-orchestrator metrics, signal activity
 */

const LearningAnalyticsDashboard = () => {
  const [selectedTab, setSelectedTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [orchestrator, setOrchestrator] = useState('flash');

  // Tab 1: Genetic Populations
  const [geneticPopulations, setGeneticPopulations] = useState(null);
  const [latestPopulation, setLatestPopulation] = useState(null);

  // Tab 2: A/B Tests
  const [abTests, setAbTests] = useState(null);
  const [activeTest, setActiveTest] = useState(null);

  // Tab 3: Behavioral Rules
  const [behavioralRules, setBehavioralRules] = useState(null);

  // Tab 4: Cascading Signals
  const [cascadingSignals, setCascadingSignals] = useState(null);

  const tenantId = localStorage.getItem('tenant_id') || '1';
  const apiBaseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8081';

  // Fetch genetic populations data
  const fetchGeneticPopulations = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/genetic-populations/${orchestrator}?tenant_id=${tenantId}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setGeneticPopulations(data);
      }
    } catch (error) {
      console.error('Error fetching genetic populations:', error);
    }

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/genetic-populations/${orchestrator}/latest?tenant_id=${tenantId}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setLatestPopulation(data);
      }
    } catch (error) {
      console.error('Error fetching latest population:', error);
    }
    setLoading(false);
  };

  // Fetch A/B tests data
  const fetchAbTests = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/ab-tests/${orchestrator}?tenant_id=${tenantId}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setAbTests(data);
      }
    } catch (error) {
      console.error('Error fetching A/B tests:', error);
    }

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/ab-tests/${orchestrator}/active?tenant_id=${tenantId}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setActiveTest(data.active_test);
      }
    } catch (error) {
      console.error('Error fetching active A/B test:', error);
    }
    setLoading(false);
  };

  // Fetch behavioral rules data
  const fetchBehavioralRules = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/behavioral-rules/${orchestrator}?tenant_id=${tenantId}&is_active=true`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setBehavioralRules(data);
      }
    } catch (error) {
      console.error('Error fetching behavioral rules:', error);
    }
    setLoading(false);
  };

  // Fetch cascading signals data
  const fetchCascadingSignals = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/learning/cascading-signals/recent?tenant_id=${tenantId}&limit=50`,
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      if (response.ok) {
        const data = await response.json();
        setCascadingSignals(data);
      }
    } catch (error) {
      console.error('Error fetching cascading signals:', error);
    }
    setLoading(false);
  };

  // Load data based on active tab
  useEffect(() => {
    if (selectedTab === 0) {
      fetchGeneticPopulations();
    } else if (selectedTab === 1) {
      fetchAbTests();
    } else if (selectedTab === 2) {
      fetchBehavioralRules();
    } else if (selectedTab === 3) {
      fetchCascadingSignals();
    }
  }, [selectedTab, orchestrator]);

  return (
    <Container className="learning-analytics-dashboard">
      <div className="dashboard-header">
        <h1>
          <Icon name="analytics" className="header-icon" />
          Autonomous Learning System Analytics
        </h1>
        <div className="orchestrator-selector">
          <label>Orchestrator:</label>
          <select
            value={orchestrator}
            onChange={(e) => setOrchestrator(e.target.value)}
            className="orchestrator-dropdown"
          >
            <option value="thunder">Thunder</option>
            <option value="flash">Flash</option>
            <option value="interview">Interview</option>
            <option value="offer">Offer</option>
            <option value="finance">Finance</option>
          </select>
        </div>
      </div>

      {loading && <Spinner description="Loading analytics data..." />}

      <TabList>
        <Tab label="Genetic Populations" />
        <Tab label="A/B Tests" />
        <Tab label="Behavioral Rules" />
        <Tab label="Cascading Signals" />
      </TabList>

      {/* TAB 1: GENETIC POPULATIONS */}
      <Panel hidden={selectedTab !== 0}>
        <div className="tab-content">
          {!geneticPopulations ? (
            <MessageBox kind="info">No genetic population data available</MessageBox>
          ) : (
            <div className="genetic-populations-view">
              {latestPopulation && (
                <Card className="latest-population-card">
                  <h3>Latest Generation (G{latestPopulation.generation_number})</h3>
                  <div className="population-stats">
                    <div className="stat">
                      <span className="stat-label">Average Fitness:</span>
                      <span className="stat-value">{latestPopulation.average_fitness.toFixed(4)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Population Size:</span>
                      <span className="stat-value">{latestPopulation.population_size}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Status:</span>
                      <span className={`stat-value status-${latestPopulation.status.toLowerCase()}`}>
                        {latestPopulation.status}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Converged:</span>
                      <span className="stat-value">{latestPopulation.has_converged ? 'Yes' : 'No'}</span>
                    </div>
                  </div>

                  {latestPopulation.chromosomes && latestPopulation.chromosomes.length > 0 && (
                    <div className="chromosomes-table">
                      <h4>Chromosomes (Top 10 by Fitness)</h4>
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableCell>Rank</TableCell>
                            <TableCell>Chromosome ID</TableCell>
                            <TableCell>Fitness Score</TableCell>
                            <TableCell>Accuracy</TableCell>
                            <TableCell>Calibration</TableCell>
                            <TableCell>Elite</TableCell>
                            <TableCell>Best</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {latestPopulation.chromosomes.slice(0, 10).map((c, idx) => (
                            <TableRow key={c.chromosome_id}>
                              <TableCell>{idx + 1}</TableCell>
                              <TableCell>{c.chromosome_id.substring(0, 8)}...</TableCell>
                              <TableCell>{c.fitness_score.toFixed(4)}</TableCell>
                              <TableCell>{(c.accuracy * 100).toFixed(1)}%</TableCell>
                              <TableCell>{(c.calibration * 100).toFixed(1)}%</TableCell>
                              <TableCell>{c.is_elite ? '✓' : '—'}</TableCell>
                              <TableCell>{c.is_best_performer ? '★' : '—'}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </Card>
              )}

              {geneticPopulations.generations && geneticPopulations.generations.length > 0 && (
                <Card className="generation-history-card">
                  <h3>Generation History (Fitness Trend)</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={geneticPopulations.generations}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="generation_number"
                        label={{ value: 'Generation', position: 'insideBottomRight', offset: -5 }}
                      />
                      <YAxis
                        label={{ value: 'Average Fitness', angle: -90, position: 'insideLeft' }}
                      />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="average_fitness"
                        stroke="#0f62fe"
                        name="Avg Fitness"
                      />
                      <Line
                        type="monotone"
                        dataKey="best_performer_fitness"
                        stroke="#24a148"
                        name="Best Performer"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Card>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* TAB 2: A/B TESTS */}
      <Panel hidden={selectedTab !== 1}>
        <div className="tab-content">
          {!activeTest && !abTests?.tests ? (
            <MessageBox kind="info">No A/B test data available</MessageBox>
          ) : (
            <div className="ab-tests-view">
              {activeTest && (
                <Card className="active-test-card">
                  <h3>Active A/B Test: {activeTest.test_id.substring(0, 8)}...</h3>
                  <div className="test-stats">
                    <div className="stat">
                      <span className="stat-label">Stage:</span>
                      <span className={`stat-value stage-${activeTest.current_stage.toLowerCase()}`}>
                        {activeTest.current_stage}
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Baseline Accuracy:</span>
                      <span className="stat-value">{(activeTest.baseline_accuracy * 100).toFixed(1)}%</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Variant Accuracy:</span>
                      <span className="stat-value">{(activeTest.variant_accuracy * 100).toFixed(1)}%</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Formation Health:</span>
                      <span className={`stat-value health-${activeTest.variant_formation_health >= 0.7 ? 'good' : 'warning'}`}>
                        {(activeTest.variant_formation_health * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {activeTest.decisions && (
                    <div className="allocation-chart">
                      <h4>Thompson Sampling Allocation</h4>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={[
                          {
                            name: 'Traffic Allocation',
                            baseline: activeTest.allocation.baseline_allocation * 100,
                            variant: activeTest.allocation.variant_allocation * 100,
                          }
                        ]}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis label={{ value: 'Allocation %', angle: -90, position: 'insideLeft' }} />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="baseline" stackId="a" fill="#0f62fe" name="Baseline" />
                          <Bar dataKey="variant" stackId="a" fill="#24a148" name="Variant" />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="decision-stats">
                        <div className="decision-stat">
                          <span>Baseline Decisions:</span>
                          <span className="value">{activeTest.decisions.baseline}</span>
                        </div>
                        <div className="decision-stat">
                          <span>Variant Decisions:</span>
                          <span className="value">{activeTest.decisions.variant}</span>
                        </div>
                        <div className="decision-stat">
                          <span>Total Decisions:</span>
                          <span className="value">{activeTest.decisions.total}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {abTests?.tests && abTests.tests.length > 0 && (
                <Card className="test-history-card">
                  <h3>A/B Test History</h3>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Test ID</TableCell>
                        <TableCell>Stage</TableCell>
                        <TableCell>Baseline Accuracy</TableCell>
                        <TableCell>Variant Accuracy</TableCell>
                        <TableCell>Rolled Back</TableCell>
                        <TableCell>Created</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {abTests.tests.map((test) => (
                        <TableRow key={test.test_id}>
                          <TableCell>{test.test_id.substring(0, 8)}...</TableCell>
                          <TableCell>{test.current_stage}</TableCell>
                          <TableCell>{(test.baseline_accuracy * 100).toFixed(1)}%</TableCell>
                          <TableCell>{(test.variant_accuracy * 100).toFixed(1)}%</TableCell>
                          <TableCell>{test.rolled_back ? 'Yes' : 'No'}</TableCell>
                          <TableCell>{new Date(test.created_at).toLocaleDateString()}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Card>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* TAB 3: BEHAVIORAL RULES */}
      <Panel hidden={selectedTab !== 2}>
        <div className="tab-content">
          {!behavioralRules?.rules || behavioralRules.rules.length === 0 ? (
            <MessageBox kind="info">No behavioral rules configured</MessageBox>
          ) : (
            <div className="behavioral-rules-view">
              {behavioralRules.rules.map((rule) => (
                <Card key={rule.rule_id} className="rule-card">
                  <div className="rule-header">
                    <h4>{rule.rule_name}</h4>
                    <span className={`rule-status ${rule.is_active ? 'active' : 'inactive'}`}>
                      {rule.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="rule-description">{rule.rule_description}</p>

                  <div className="rule-details">
                    <div className="detail">
                      <span className="label">Trigger:</span>
                      <span className="value">
                        {rule.trigger_metric} {rule.trigger_operator} {rule.trigger_threshold}
                      </span>
                    </div>
                    <div className="detail">
                      <span className="label">Action:</span>
                      <span className="value">{rule.action_type}</span>
                    </div>
                    <div className="detail">
                      <span className="label">Triggered:</span>
                      <span className="value">{rule.triggered_count} times</span>
                    </div>
                    <div className="detail">
                      <span className="label">Last Triggered:</span>
                      <span className="value">
                        {rule.last_triggered_at ? new Date(rule.last_triggered_at).toLocaleString() : 'Never'}
                      </span>
                    </div>
                  </div>

                  {rule.recent_executions && rule.recent_executions.length > 0 && (
                    <div className="recent-executions">
                      <h5>Recent Executions</h5>
                      <ul>
                        {rule.recent_executions.map((exec) => (
                          <li key={exec.execution_id}>
                            <span className={`status-${exec.status.toLowerCase()}`}>{exec.status}</span>
                            {new Date(exec.triggered_at).toLocaleString()}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      </Panel>

      {/* TAB 4: CASCADING SIGNALS */}
      <Panel hidden={selectedTab !== 3}>
        <div className="tab-content">
          {!cascadingSignals?.signals || cascadingSignals.signals.length === 0 ? (
            <MessageBox kind="info">No cascading signals</MessageBox>
          ) : (
            <div className="cascading-signals-view">
              <Card className="signals-list-card">
                <h3>Recent Cascading Signals ({cascadingSignals.total_signals})</h3>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Source</TableCell>
                      <TableCell>Target</TableCell>
                      <TableCell>Metric</TableCell>
                      <TableCell>Value</TableCell>
                      <TableCell>Severity</TableCell>
                      <TableCell>Timeline (min)</TableCell>
                      <TableCell>Sent</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {cascadingSignals.signals.map((signal) => (
                      <TableRow key={signal.signal_id}>
                        <TableCell>{signal.source_orchestrator}</TableCell>
                        <TableCell>{signal.target_orchestrator}</TableCell>
                        <TableCell>{signal.metric_name}</TableCell>
                        <TableCell>{signal.metric_current_value.toFixed(2)}</TableCell>
                        <TableCell>
                          <span className={`severity-${signal.cascade_impact_severity.toLowerCase()}`}>
                            {signal.cascade_impact_severity}
                          </span>
                        </TableCell>
                        <TableCell>{signal.cascade_impact_timeline_minutes}</TableCell>
                        <TableCell>{new Date(signal.sent_at).toLocaleString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </div>
          )}
        </div>
      </Panel>
    </Container>
  );
};

export default LearningAnalyticsDashboard;
