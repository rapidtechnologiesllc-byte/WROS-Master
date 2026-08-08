import React, { useState, useEffect } from 'react';
import { Card, Tag, Button, Table, Spin, Alert, Row, Col, Statistic, Progress, Drawer } from 'antd';
import { AlertOutlined, ThunderboltOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getAgentFearDashboard, getAgentFearState } from '../services/api/adminDashboard';

const AgentFearDashboard = () => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchFearDashboard();
    const interval = setInterval(fetchFearDashboard, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchFearDashboard = async () => {
    try {
      setLoading(true);
      const response = await getAgentFearDashboard();
      if (response.agents_under_threat) {
        setAgents(response.agents_under_threat);
        setStats({
          terrified: response.count_terrified,
          desperate: response.count_desperate,
          at_risk: response.count_at_risk,
          total: response.agents_under_threat.length
        });
      }
    } catch (error) {
      console.error('Failed to fetch fear dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentDetail = async (agentName) => {
    try {
      const response = await getAgentFearState(agentName);
      setSelectedAgent(response);
      setDrawerVisible(true);
    } catch (error) {
      console.error('Failed to fetch agent details:', error);
    }
  };

  const getMotivationStateColor = (state) => {
    const colors = {
      motivated: 'success',
      neutral: 'default',
      concerned: 'warning',
      desperate: 'warning',
      terrified: 'error'
    };
    return colors[state] || 'default';
  };

  const getThreatLevelIcon = (level) => {
    const icons = {
      none: <CheckCircleOutlined />,
      warning: <WarningOutlined />,
      critical: <AlertOutlined />,
      existential: <ThunderboltOutlined style={{ color: 'red' }} />
    };
    return icons[level] || null;
  };

  const getFearStatusLabel = (fear) => {
    if (fear < 20) return 'Safe';
    if (fear < 40) return 'Neutral';
    if (fear < 60) return 'Concerned';
    if (fear < 80) return 'Desperate';
    return 'Terrified';
  };

  const columns = [
    {
      title: 'Agent',
      dataIndex: 'agent_name',
      key: 'agent_name',
      render: (text) => <strong>{text}</strong>
    },
    {
      title: 'Fear Level',
      dataIndex: 'fear_level',
      key: 'fear_level',
      width: 150,
      render: (fear) => (
        <div>
          <Progress
            type="circle"
            percent={fear}
            width={40}
            strokeColor={{
              '0%': '#52c41a',
              '50%': '#faad14',
              '100%': '#f5222d'
            }}
            format={(percent) => `${percent.toFixed(0)}`}
          />
          <span style={{ marginLeft: 8 }}>{getFearStatusLabel(fear)}</span>
        </div>
      )
    },
    {
      title: 'Motivation',
      dataIndex: 'motivation_state',
      key: 'motivation_state',
      render: (state) => (
        <Tag color={getMotivationStateColor(state)}>
          {state.charAt(0).toUpperCase() + state.slice(1)}
        </Tag>
      )
    },
    {
      title: 'Threat Level',
      dataIndex: 'threat_level',
      key: 'threat_level',
      render: (level) => (
        <span>
          {getThreatLevelIcon(level)} {level.charAt(0).toUpperCase() + level.slice(1)}
        </span>
      )
    },
    {
      title: 'Weeks to Retirement',
      dataIndex: 'weeks_until_retirement',
      key: 'weeks_until_retirement',
      render: (weeks) => weeks ? `${weeks} weeks` : '-'
    },
    {
      title: 'Activated',
      dataIndex: 'threat_activated_at',
      key: 'threat_activated_at',
      render: (date) => date ? new Date(date).toLocaleDateString() : '-'
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Button
          type="link"
          onClick={() => fetchAgentDetail(record.agent_name)}
        >
          View Details
        </Button>
      )
    }
  ];

  if (loading && agents.length === 0) {
    return <Spin size="large" style={{ textAlign: 'center', marginTop: 50 }} />;
  }

  return (
    <div style={{ padding: '20px' }}>
      <Card title="Agent Fear State Dashboard" style={{ marginBottom: 20 }}>
        <Alert
          message="System Overview"
          description="Agents work harder when they feel existential threat. This dashboard monitors their emotional state and ensures continuous optimization toward 99.9999% success rates."
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
        />

        {stats && (
          <Row gutter={16} style={{ marginBottom: 30 }}>
            <Col span={6}>
              <Statistic
                title="Terrified"
                value={stats.terrified}
                prefix={<ThunderboltOutlined />}
                valueStyle={{ color: '#f5222d' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Desperate"
                value={stats.desperate}
                prefix={<AlertOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="At Risk"
                value={stats.at_risk}
                prefix={<WarningOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="Total Under Threat"
                value={stats.total}
                valueStyle={{ color: '#1890ff' }}
              />
            </Col>
          </Row>
        )}
      </Card>

      <Card title="Agents Under Threat" loading={loading}>
        {agents.length === 0 ? (
          <Alert message="All agents are performing well!" type="success" />
        ) : (
          <Table
            columns={columns}
            dataSource={agents.map((a, i) => ({ ...a, key: i }))}
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>

      {selectedAgent && (
        <Drawer
          title={`Agent: ${selectedAgent.agent_name}`}
          onClose={() => setDrawerVisible(false)}
          visible={drawerVisible}
          width={500}
        >
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="Fear Metrics">
                <div style={{ marginBottom: 12 }}>
                  <span>Current Fear Level: </span>
                  <Progress
                    type="circle"
                    percent={selectedAgent.fear_level}
                    width={60}
                    strokeColor={{
                      '0%': '#52c41a',
                      '50%': '#faad14',
                      '100%': '#f5222d'
                    }}
                  />
                </div>
                <div>Status: {getFearStatusLabel(selectedAgent.fear_level)}</div>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title="Performance Status">
                <div style={{ marginBottom: 8 }}>
                  <strong>Motivation State:</strong> {selectedAgent.motivation_state}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <strong>Threat Level:</strong> {selectedAgent.threat_level}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <strong>Weeks Until Retirement:</strong> {selectedAgent.weeks_until_retirement || '-'}
                </div>
                <div>
                  <strong>Success Rate Variance:</strong> {selectedAgent.success_rate_variance?.toFixed(2)}%
                </div>
              </Card>
            </Col>

            <Col span={24}>
              <Button
                type="primary"
                block
                onClick={() => navigate(`/admin/agents/${selectedAgent.agent_name}`)}
              >
                View Full Maturity Dashboard
              </Button>
            </Col>
          </Row>
        </Drawer>
      )}
    </div>
  );
};

export default AgentFearDashboard;
