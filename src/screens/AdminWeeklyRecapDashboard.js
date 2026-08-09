/**
 * Admin Weekly Recap Dashboard
 *
 * CEO's executive view: Everything that happened this week at a glance
 * Shows: Weekly Standup Summary, HTD Pipeline Progress, Opportunity Pipeline,
 * Partner Performance, Flash Directives, Agent Health, Forecast vs Reality
 */

import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Button, Tabs, Spin, Alert, Empty, Badge } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, TeamOutlined, DollarOutlined, CheckCircleOutlined, WarningOutlined, ThunderboltOutlined } from '@ant-design/icons';

export default function AdminWeeklyRecapDashboard() {
  const [loading, setLoading] = useState(false);
  const [weekData, setWeekData] = useState({
    week: 'Aug 4-10, 2026',
    agents_reporting: 25,
    agents_operational: 23,
    agents_degraded: 2,
    critical_alerts: 1,
    high_alerts: 3,
    partners_on_track: 2,
    partners_behind: 1,
  });

  const agentHealthColumns = [
    { title: 'Agent', dataIndex: 'name', key: 'name' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (status) => {
      const color = status === 'operational' ? 'green' : status === 'degraded' ? 'orange' : 'red';
      return <Tag color={color}>{status.toUpperCase()}</Tag>;
    }},
    { title: 'Maturity', dataIndex: 'maturity', key: 'maturity', render: (v) => `${v}%` },
    { title: 'Success Rate', dataIndex: 'success_rate', key: 'success_rate', render: (v) => `${v}%` },
  ];

  const agentHealthData = [
    { key: '1', name: 'Recruitment Agent', status: 'operational', maturity: 92, success_rate: 98 },
    { key: '2', name: 'Resource Manager', status: 'operational', maturity: 87, success_rate: 95 },
    { key: '3', name: 'Finance Agent', status: 'operational', maturity: 85, success_rate: 93 },
    { key: '4', name: 'HR Agent', status: 'operational', maturity: 89, success_rate: 96 },
    { key: '5', name: 'KPI Agent', status: 'degraded', maturity: 72, success_rate: 88 },
  ];

  const opportunityColumns = [
    { title: 'Partner', dataIndex: 'partner', key: 'partner' },
    { title: 'Week Start', dataIndex: 'week_start', key: 'week_start', render: (v) => `$${v}K` },
    { title: 'Week Closed', dataIndex: 'week_closed', key: 'week_closed', render: (v) => `$${v}K` },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (status) => (
      <Tag color={status === 'on-track' ? 'green' : 'orange'}>{status.toUpperCase()}</Tag>
    )},
  ];

  const opportunityData = [
    { key: '1', partner: 'Partner A', week_start: 120, week_closed: 45, status: 'on-track' },
    { key: '2', partner: 'Partner B', week_start: 85, week_closed: 20, status: 'at-risk' },
  ];

  const tabItems = [
    {
      key: '1',
      label: 'Weekly Summary',
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: '24px' }}>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Agents Reporting"
                  value={weekData.agents_reporting}
                  suffix="/ 25"
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Operational"
                  value={weekData.agents_operational}
                  suffix="agents"
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Degraded"
                  value={weekData.agents_degraded}
                  suffix="agents"
                  valueStyle={{ color: '#faad14' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Critical Alerts"
                  value={weekData.critical_alerts}
                  valueStyle={{ color: '#f5222d' }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="Agent Health Status" style={{ marginBottom: '24px' }}>
            <Table columns={agentHealthColumns} dataSource={agentHealthData} pagination={false} />
          </Card>
        </div>
      ),
    },
    {
      key: '2',
      label: 'Pipeline Status',
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: '24px' }}>
            <Col xs={24} sm={12}>
              <Card>
                <Statistic
                  title="Partners On Track"
                  value={weekData.partners_on_track}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12}>
              <Card>
                <Statistic
                  title="Partners Behind"
                  value={weekData.partners_behind}
                  prefix={<WarningOutlined />}
                  valueStyle={{ color: '#faad14' }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="Weekly Opportunity Pipeline">
            <Table columns={opportunityColumns} dataSource={opportunityData} pagination={false} />
          </Card>
        </div>
      ),
    },
    {
      key: '3',
      label: 'Performance',
      children: (
        <Card>
          <Alert
            message="Weekly Performance Summary"
            description="All agents performing above baseline. 3 high-priority alerts identified for week of Aug 11-17."
            type="info"
            showIcon
            style={{ marginBottom: '24px' }}
          />
          <Empty description="Performance data loading..." />
        </Card>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={8}>
          <Card>
            <Statistic
              title="Week"
              value={weekData.week}
              valueStyle={{ fontSize: '14px' }}
            />
          </Card>
        </Col>
      </Row>

      <Tabs items={tabItems} />
    </div>
  );
}
