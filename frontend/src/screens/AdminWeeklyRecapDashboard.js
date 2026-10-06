// Admin Weekly Recap -- agent health, alerts and pipeline for one week, all
// from GET /admin/weekly-recap (recorded agent runs, org-health alert counts,
// opportunities opened/won/lost). Replaces hardcoded sample data.
import React, { useEffect, useState } from "react";
import { Alert, Card, Col, Empty, Row, Select, Spin, Statistic, Table, Tabs, Tag } from "antd";
import { CheckCircleOutlined, WarningOutlined } from "@ant-design/icons";
import { getWeeklyRecap } from "../services/api/adminWeeklyRecap";

const usd = (cents) => `$${((cents || 0) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const agentColumns = [
  { title: "Agent", dataIndex: "name", key: "name" },
  {
    title: "Status", dataIndex: "status", key: "status",
    render: (status) => <Tag color={status === "operational" ? "green" : "orange"}>{status.toUpperCase()}</Tag>,
  },
  { title: "Runs", dataIndex: "runs", key: "runs" },
  { title: "Failures", dataIndex: "failures", key: "failures" },
  { title: "Success Rate", dataIndex: "success_rate", key: "success_rate", render: (v) => (v == null ? "--" : `${v}%`) },
  { title: "Maturity", dataIndex: "maturity", key: "maturity", render: (v) => (v == null ? "--" : `${Math.round(v)}%`) },
  { title: "Last Run", dataIndex: "last_run", key: "last_run", render: (v) => (v ? new Date(v).toLocaleString() : "--") },
];

const pipelineColumns = [
  { title: "Owner", dataIndex: "owner", key: "owner" },
  { title: "Opened", dataIndex: "opened", key: "opened" },
  { title: "Opened Value", dataIndex: "opened_value_usd_cents", key: "opened_value", render: usd },
  { title: "Won", dataIndex: "won", key: "won" },
  { title: "Won Value", dataIndex: "won_value_usd_cents", key: "won_value", render: usd },
  { title: "Lost", dataIndex: "lost", key: "lost" },
];

export default function AdminWeeklyRecapDashboard() {
  const [weeksBack, setWeeksBack] = useState(0);
  const [recap, setRecap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getWeeklyRecap(weeksBack)
      .then(setRecap)
      .catch((err) => setError(`Failed to load weekly recap: ${err.message}`))
      .finally(() => setLoading(false));
  }, [weeksBack]);

  if (loading) return <div style={{ padding: 24, textAlign: "center" }}><Spin /></div>;
  if (error) return <div style={{ padding: 24 }}><Alert type="error" message={error} showIcon /></div>;

  const alerts = recap.alerts || {};
  const won = recap.pipeline.reduce((sum, r) => sum + r.won_value_usd_cents, 0);
  const opened = recap.pipeline.reduce((sum, r) => sum + r.opened, 0);

  const tabItems = [
    {
      key: "agents",
      label: "Agent Health",
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={8}><Card><Statistic title="Agents Reporting" value={recap.agents_reporting} /></Card></Col>
            <Col xs={24} sm={8}><Card><Statistic title="Operational" value={recap.agents_operational} valueStyle={{ color: "#52c41a" }} prefix={<CheckCircleOutlined />} /></Card></Col>
            <Col xs={24} sm={8}><Card><Statistic title="Degraded" value={recap.agents_degraded} valueStyle={{ color: "#faad14" }} prefix={<WarningOutlined />} /></Card></Col>
          </Row>
          <Card title="Agent runs this week">
            {recap.agents.length ? (
              <Table rowKey="name" columns={agentColumns} dataSource={recap.agents} pagination={false} />
            ) : (
              <Empty description="No agent runs recorded this week" />
            )}
          </Card>
        </div>
      ),
    },
    {
      key: "alerts",
      label: "Alerts",
      children: (
        <Row gutter={16}>
          <Col xs={24} sm={12} md={8}><Card><Statistic title="Critical interventions" value={alerts.intervention_critical} valueStyle={{ color: "#f5222d" }} /></Card></Col>
          <Col xs={24} sm={12} md={8}><Card><Statistic title="High interventions" value={alerts.intervention_high} valueStyle={{ color: "#faad14" }} /></Card></Col>
          <Col xs={24} sm={12} md={8}><Card><Statistic title="Active SLA breaches" value={alerts.active_sla_breaches} /></Card></Col>
          <Col xs={24} sm={12} md={8} style={{ marginTop: 16 }}><Card><Statistic title="Escalated overdue tasks" value={alerts.escalated_overdue_tasks} /></Card></Col>
          <Col xs={24} sm={12} md={8} style={{ marginTop: 16 }}><Card><Statistic title="Open capacity alerts" value={alerts.open_capacity_alerts} /></Card></Col>
        </Row>
      ),
    },
    {
      key: "pipeline",
      label: "Pipeline",
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12}><Card><Statistic title="Opportunities opened" value={opened} /></Card></Col>
            <Col xs={24} sm={12}><Card><Statistic title="Won this week" value={usd(won)} valueStyle={{ color: "#52c41a" }} /></Card></Col>
          </Row>
          <Card title="By owner">
            {recap.pipeline.length ? (
              <Table rowKey="owner" columns={pipelineColumns} dataSource={recap.pipeline} pagination={false} />
            ) : (
              <Empty description="No opportunities opened, won or lost this week" />
            )}
          </Card>
        </div>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={16} align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Statistic title="Week" value={`${recap.week_start} to ${recap.week_end}`} valueStyle={{ fontSize: 16 }} />
        </Col>
        <Col>
          <Select
            value={weeksBack}
            onChange={setWeeksBack}
            style={{ width: 160 }}
            options={[0, 1, 2, 3, 4].map((n) => ({ value: n, label: n === 0 ? "This week" : n === 1 ? "Last week" : `${n} weeks ago` }))}
          />
        </Col>
      </Row>
      <Tabs items={tabItems} />
    </div>
  );
}
