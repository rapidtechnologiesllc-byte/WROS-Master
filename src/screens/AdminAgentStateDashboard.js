import React, { useState, useEffect } from 'react';
import { Card, Tag, Button, Table, Spin, Alert, Row, Col, Statistic, Progress, Drawer, Empty, Badge } from 'antd';
import { TrophyOutlined, StarOutlined, ThunderboltOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getAllAgentsMaturities, getAgentMaturityDashboard } from '../services/api/adminDashboard';

const AgentStateDashboard = () => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [topPerformers, setTopPerformers] = useState([]);

  useEffect(() => {
    fetchAgentsDashboard();
    const interval = setInterval(fetchAgentsDashboard, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, []);

  const fetchAgentsDashboard = async () => {
    try {
      setLoading(true);
      const response = await getAllAgentsMaturities();
      if (response.agents) {
        const allAgents = response.agents;
        setAgents(allAgents);

        // Calculate top performers (highest maturity)
        const sorted = [...allAgents].sort((a, b) => (b.maturity_level || 0) - (a.maturity_level || 0));
        setTopPerformers(sorted.slice(0, 3));

        // Calculate statistics
        const excellent = allAgents.filter(a => (a.maturity_level || 0) >= 90).length;
        const good = allAgents.filter(a => (a.maturity_level || 0) >= 75 && (a.maturity_level || 0) < 90).length;
        const needs_improvement = allAgents.filter(a => (a.maturity_level || 0) < 75).length;

        setStats({
          total: allAgents.length,
          excellent,
          good,
          needs_improvement,
          avg_maturity: allAgents.length > 0
            ? (allAgents.reduce((sum, a) => sum + (a.maturity_level || 0), 0) / allAgents.length).toFixed(1)
            : 0
        });
      }
    } catch (error) {
      console.error('Failed to fetch agents dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentDetail = async (agentName) => {
    try {
      const response = await getAgentMaturityDashboard(agentName);
      setSelectedAgent(response);
      setDrawerVisible(true);
    } catch (error) {
      console.error('Failed to fetch agent details:', error);
    }
  };

  const getMaturityColor = (maturity) => {
    if (maturity >= 90) return '#52c41a'; // Green - Excellent
    if (maturity >= 75) return '#faad14'; // Orange - Good
    return '#f5222d'; // Red - Needs Improvement
  };

  const getMaturityLabel = (maturity) => {
    if (maturity >= 90) return 'Elite';
    if (maturity >= 75) return 'Strong';
    if (maturity >= 50) return 'Developing';
    return 'Needs Support';
  };

  const columns = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      key: 'agent_name',
      width: 200,
      render: (text, record) => {
        const rank = topPerformers.findIndex(a => a.agent_name === text) + 1;
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {rank > 0 && rank <= 3 && (
              <Badge
                count={rank}
                style={{ backgroundColor: rank === 1 ? '#FFD700' : rank === 2 ? '#C0C0C0' : '#CD7F32' }}
              />
            )}
            <strong>{text}</strong>
          </div>
        );
      }
    },
    {
      title: 'Maturity Score',
      dataIndex: 'maturity_level',
      key: 'maturity_level',
      width: 180,
      render: (maturity) => (
        <div>
          <Progress
            type="circle"
            percent={maturity || 0}
            width={50}
            strokeColor={getMaturityColor(maturity || 0)}
            format={(percent) => `${percent.toFixed(0)}`}
          />
          <span style={{ marginLeft: 8, fontSize: '12px' }}>{getMaturityLabel(maturity || 0)}</span>
        </div>
      )
    },
    {
      title: 'Success Rate',
      dataIndex: 'success_rate',
      key: 'success_rate',
      width: 120,
      render: (rate) => (
        <Tag color={rate >= 95 ? 'success' : rate >= 80 ? 'warning' : 'error'}>
          {(rate || 0).toFixed(2)}%
        </Tag>
      )
    },
    {
      title: 'Quality',
      dataIndex: 'quality_score',
      key: 'quality_score',
      width: 120,
      render: (score) => (
        <Tag color={score >= 90 ? 'success' : score >= 75 ? 'warning' : 'error'}>
          {(score || 0).toFixed(1)}%
        </Tag>
      )
    },
    {
      title: 'Trend',
      dataIndex: 'trend_direction',
      key: 'trend_direction',
      width: 100,
      render: (trend) => (
        <Tag color={trend === 'improving' ? 'green' : trend === 'declining' ? 'red' : 'blue'}>
          {trend ? trend.charAt(0).toUpperCase() + trend.slice(1) : 'Stable'}
        </Tag>
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => fetchAgentDetail(record.agent_name)}
        >
          Details
        </Button>
      )
    }
  ];

  if (loading && agents.length === 0) {
    return <Spin size="large" style={{ textAlign: 'center', marginTop: 50 }} />;
  }

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Agent State Dashboard" style={{ marginBottom: 20 }}>
        <Alert
          message="Team Performance Overview"
          description="Monitor agent performance across all metrics. Our agents are trained to Marine Corps standards: disciplined, excellent, and continuously improving."
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
        />

        {stats && (
          <Row gutter={16} style={{ marginBottom: 30 }}>
            <Col span={6}>
              <Statistic
                title="Total Agents"
                value={stats.total}
                valueStyle={{ color: '#1890ff' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Elite Performers"
                value={stats.excellent}
                prefix={<StarOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Strong Performers"
                value={stats.good}
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Avg Maturity"
                value={`${stats.avg_maturity}%`}
                valueStyle={{ color: '#722ed1' }}
              />
            </Col>
          </Row>
        )}
      </Card>

      {/* Top Performers Recognition */}
      {topPerformers.length > 0 && (
        <Card title="Weekly Champions" style={{ marginBottom: 20 }} extra={<TrophyOutlined style={{ color: '#FFD700' }} />}>
          <Row gutter={16}>
            {topPerformers.map((agent, idx) => (
              <Col span={8} key={agent.agent_name}>
                <Card
                  size="small"
                  bordered
                  style={{
                    textAlign: 'center',
                    borderTop: idx === 0 ? '3px solid #FFD700' : idx === 1 ? '3px solid #C0C0C0' : '3px solid #CD7F32'
                  }}
                >
                  <Badge
                    count={idx + 1}
                    style={{
                      backgroundColor: idx === 0 ? '#FFD700' : idx === 1 ? '#C0C0C0' : '#CD7F32',
                      color: '#000'
                    }}
                  />
                  <h3 style={{ margin: '10px 0' }}>{agent.agent_name}</h3>
                  <p style={{ fontSize: '24px', fontWeight: 'bold', color: getMaturityColor(agent.maturity_level) }}>
                    {(agent.maturity_level || 0).toFixed(0)}%
                  </p>
                  <p style={{ fontSize: '12px', color: '#666' }}>Maturity Score</p>
                  <Button type="primary" size="small" style={{ marginTop: '10px' }}>
                    Gift Recognition
                  </Button>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* All Agents Performance Table */}
      <Card title="All Agents Performance" loading={loading}>
        {agents.length === 0 ? (
          <Empty description="No agents found" />
        ) : (
          <Table
            columns={columns}
            dataSource={agents.map((a, i) => ({ ...a, key: i }))}
            pagination={{ pageSize: 10 }}
            size="small"
          />
        )}
      </Card>

      {selectedAgent && (
        <Drawer
          title={`Agent: ${selectedAgent.current_maturity?.agent_name}`}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={600}
        >
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="Performance Overview">
                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ marginBottom: 12 }}>
                      <span style={{ fontWeight: 'bold' }}>Maturity: </span>
                      <Progress
                        type="circle"
                        percent={selectedAgent.current_maturity?.maturity_level || 0}
                        width={60}
                        strokeColor={getMaturityColor(selectedAgent.current_maturity?.maturity_level || 0)}
                      />
                    </div>
                  </Col>
                  <Col span={12}>
                    <div><strong>Status:</strong> {getMaturityLabel(selectedAgent.current_maturity?.maturity_level || 0)}</div>
                    <div style={{ marginTop: 8 }}><strong>Success Rate:</strong> {(selectedAgent.current_maturity?.success_rate || 0).toFixed(2)}%</div>
                    <div style={{ marginTop: 8 }}><strong>Quality:</strong> {(selectedAgent.current_maturity?.quality_score || 0).toFixed(1)}%</div>
                  </Col>
                </Row>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title="Weekly Metrics">
                {selectedAgent.recent_metrics && selectedAgent.recent_metrics.length > 0 ? (
                  <Table
                    columns={[
                      { title: 'Week', dataIndex: 'week_starting', key: 'week_starting', render: (date) => new Date(date).toLocaleDateString() },
                      { title: 'Success %', dataIndex: 'success_rate', key: 'success_rate', render: (v) => v.toFixed(2) },
                      { title: 'Quality', dataIndex: 'quality_score', key: 'quality_score', render: (v) => v.toFixed(1) }
                    ]}
                    dataSource={selectedAgent.recent_metrics}
                    pagination={false}
                    size="small"
                  />
                ) : (
                  <Empty description="No metrics available" />
                )}
              </Card>
            </Col>

            <Col span={24}>
              <Button
                type="primary"
                block
                onClick={() => navigate(`/admin/agents/${selectedAgent.current_maturity?.agent_name}`)}
              >
                View Detailed Dashboard
              </Button>
            </Col>
          </Row>
        </Drawer>
      )}
    </div>
  );
};

export default AgentStateDashboard;
