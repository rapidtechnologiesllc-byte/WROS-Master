import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Tabs, Spin, Alert, Button, Space } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, ClockCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiCall } from '../utils/api';

const AdminAgentStandupsDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(30000);

  const fetchStandupData = async () => {
    try {
      setLoading(true);
      const response = await apiCall('GET', '/admin/agent-standups/dashboard');
      setData(response);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch standup data');
      console.error('Standup fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStandupData();
    const interval = setInterval(fetchStandupData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'failing': return 'error';
      case 'not_running': return 'red';
      default: return 'default';
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'ok': return 'success';
      case 'warning': return 'warning';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  if (loading && !data) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <Spin size="large" tip="Loading Agent Standups..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <Alert
          message="Error Loading Agent Standups"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchStandupData}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const standup = data?.daily_standup || {};
  const scrum = data?.scrum_of_scrums || {};

  // Prepare agent reports table data
  const agentReportsColumns = [
    {
      title: 'Agent Name',
      dataIndex: 'agent_name',
      key: 'agent_name',
      width: '15%',
    },
    {
      title: 'Tier',
      dataIndex: 'tier',
      key: 'tier',
      width: '12%',
      render: (tier) => {
        const tierLabel = tier?.replace('tier_', '').replace('_', ' ').toUpperCase();
        return <Tag>{tierLabel}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: '10%',
      render: (status) => (
        <Tag color={getStatusColor(status)}>
          {status?.replace('_', ' ').toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: '10%',
      render: (severity) => (
        <Tag color={getSeverityColor(severity)}>
          {severity?.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Executions',
      dataIndex: 'executions',
      key: 'executions',
      width: '10%',
      align: 'center',
    },
    {
      title: 'Success Rate',
      dataIndex: 'success_rate',
      key: 'success_rate',
      width: '10%',
      align: 'center',
      render: (rate) => `${rate}%`,
    },
    {
      title: 'Avg Duration (ms)',
      dataIndex: 'avg_duration_ms',
      key: 'avg_duration_ms',
      width: '10%',
      align: 'center',
    },
    {
      title: 'Concerns',
      dataIndex: 'validation_concerns',
      key: 'validation_concerns',
      width: '23%',
      render: (concerns) => (
        <div style={{ fontSize: '12px' }}>
          {concerns && concerns.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: '20px' }}>
              {concerns.map((concern, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>
                  <span style={{ color: '#ff4d4f', fontWeight: 'bold' }}>
                    ⚠️ {concern.question}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <span style={{ color: '#52c41a' }}>✓ No concerns</span>
          )}
        </div>
      ),
    },
  ];

  // Prepare tier summary
  const tierSummaryData = standup.tier_summary
    ? Object.entries(standup.tier_summary).map(([tier, stats]) => ({
        key: tier,
        tier: tier?.replace('tier_', '').replace('_', ' ').toUpperCase(),
        agent_count: stats.agent_count,
        healthy: stats.healthy,
        degraded: stats.degraded,
        failing: stats.failing,
        not_running: stats.not_running,
      }))
    : [];

  const tierSummaryColumns = [
    { title: 'Tier', dataIndex: 'tier', key: 'tier' },
    { title: 'Total Agents', dataIndex: 'agent_count', key: 'agent_count', align: 'center' },
    {
      title: 'Healthy',
      dataIndex: 'healthy',
      key: 'healthy',
      align: 'center',
      render: (h) => <span style={{ color: '#52c41a', fontWeight: 'bold' }}>{h}</span>,
    },
    {
      title: 'Degraded',
      dataIndex: 'degraded',
      key: 'degraded',
      align: 'center',
      render: (d) => <span style={{ color: '#faad14', fontWeight: 'bold' }}>{d}</span>,
    },
    {
      title: 'Failing',
      dataIndex: 'failing',
      key: 'failing',
      align: 'center',
      render: (f) => <span style={{ color: '#f5222d', fontWeight: 'bold' }}>{f}</span>,
    },
    {
      title: 'Not Running',
      dataIndex: 'not_running',
      key: 'not_running',
      align: 'center',
      render: (nr) => <span style={{ color: '#ff4d4f', fontWeight: 'bold' }}>{nr}</span>,
    },
  ];

  // Prepare CEO directives
  const ceoDirectives = scrum.ceo_directives || [];
  const ceoDirectivesColumns = [
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: '10%',
      render: (severity) => (
        <Tag color={getSeverityColor(severity)}>
          {severity?.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Directive',
      dataIndex: 'directive',
      key: 'directive',
      width: '50%',
    },
    {
      title: 'Owner',
      dataIndex: 'owner',
      key: 'owner',
      width: '20%',
    },
    {
      title: 'Deadline',
      dataIndex: 'deadline',
      key: 'deadline',
      width: '20%',
      render: (deadline) => <Tag color="blue">{deadline}</Tag>,
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>🤖 Agent Standups & Scrum of Scrums</h1>
        <Space>
          <span style={{ fontSize: '12px', color: '#999' }}>
            Auto-refresh: {refreshInterval / 1000}s
          </span>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={fetchStandupData}
            loading={loading}
          >
            Refresh
          </Button>
        </Space>
      </div>

      {/* Daily Standup Summary */}
      <Card title="📊 Daily Standup Report" style={{ marginBottom: '20px' }} loading={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="Standup Time"
              value={standup.standup_time || '8:00 AM EST'}
              prefix={<ClockCircleOutlined />}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="Agents Reporting"
              value={standup.total_agents_reporting || 0}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="Standup Date"
              value={standup.date || 'N/A'}
            />
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Statistic
              title="Issues Requiring Review"
              value={standup.ceo_focus_areas?.length || 0}
              valueStyle={{ color: standup.ceo_focus_areas?.length > 0 ? '#ff4d4f' : '#52c41a' }}
            />
          </Col>
        </Row>

        {standup.ceo_focus_areas && standup.ceo_focus_areas.length > 0 && (
          <Alert
            style={{ marginTop: '20px' }}
            message="⚠️ CRITICAL FOCUS AREAS FOR CEO"
            description={
              <ul style={{ margin: '10px 0', paddingLeft: '20px' }}>
                {standup.ceo_focus_areas.map((area, idx) => (
                  <li key={idx}>{area}</li>
                ))}
              </ul>
            }
            type="error"
            showIcon
          />
        )}
      </Card>

      {/* Tier Summary */}
      <Card title="📈 Agent Health by Tier" style={{ marginBottom: '20px' }} loading={loading}>
        <Table
          columns={tierSummaryColumns}
          dataSource={tierSummaryData}
          pagination={false}
          size="small"
          scroll={{ x: true }}
        />
      </Card>

      {/* Scrum of Scrums */}
      <Card title="🎯 Scrum of Scrums (8:30 AM EST)" style={{ marginBottom: '20px' }} loading={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="Flash Executions"
                value={scrum.flash_status?.executions || 0}
                prefix={<ClockCircleOutlined />}
              />
              <div style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
                Success Rate: {scrum.flash_status?.success_rate || 0}%
              </div>
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="Thunder Recruitment"
                value={scrum.thunder_recruitment?.executions || 0}
              />
              <div style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
                Daily Target: {scrum.thunder_recruitment?.daily_target || 20}
              </div>
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="Critical Directives"
                value={scrum.critical_focus || 0}
                valueStyle={{ color: scrum.critical_focus > 0 ? '#ff4d4f' : '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title="Strategic Target"
                value="2030"
                suffix="Goal"
              />
              <div style={{ marginTop: '10px', fontSize: '11px', color: '#666' }}>
                $100M Revenue / 2000 Employees
              </div>
            </Card>
          </Col>
        </Row>

        {scrum.ceo_directives && scrum.ceo_directives.length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <h3 style={{ marginBottom: '10px' }}>📋 CEO Directives</h3>
            <Table
              columns={ceoDirectivesColumns}
              dataSource={ceoDirectives.map((d, idx) => ({ ...d, key: idx }))}
              pagination={false}
              size="small"
              scroll={{ x: true }}
            />
          </div>
        )}
      </Card>

      {/* Detailed Agent Reports */}
      <Card title="🔍 Detailed Agent Reports" style={{ marginBottom: '20px' }} loading={loading}>
        <Table
          columns={agentReportsColumns}
          dataSource={standup.agent_reports?.map((r, idx) => ({ ...r, key: idx })) || []}
          pagination={{ pageSize: 10, total: standup.agent_reports?.length || 0 }}
          scroll={{ x: true }}
          size="small"
        />
      </Card>

      {/* Flash Accountability */}
      {scrum.flash_accountability && (
        <Alert
          style={{ marginBottom: '20px' }}
          message="⚡ Flash Accountability"
          description={scrum.flash_accountability}
          type="info"
          showIcon
        />
      )}

      <div style={{ textAlign: 'center', color: '#999', fontSize: '12px', marginTop: '20px' }}>
        Last updated: {new Date().toLocaleTimeString()} | Auto-refreshes every {refreshInterval / 1000} seconds
      </div>
    </div>
  );
};

export default AdminAgentStandupsDashboard;
