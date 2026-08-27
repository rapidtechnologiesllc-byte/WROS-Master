import { useEffect, useState } from "react";
import {
  Card,
  Table,
  Tag,
  Button,
  Drawer,
  Statistic,
  Row,
  Col,
  Space,
  Spin,
  Empty,
  message,
  Badge,
  Progress,
  Tabs,
  Alert,
} from "antd";
import {
  ReloadOutlined,
  DeleteOutlined,
  RedoOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import styled from "styled-components";
import { apiRequest } from "../services/api/client";

const PageContainer = styled.div`
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
`;

const StatsContainer = styled.div`
  margin-bottom: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
`;

function MessageQueueDashboard() {
  const [tasks, setTasks] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [health, setHealth] = useState({
    database: 'unknown',
    messageQueue: 'unknown',
    slmService: 'unknown',
    doctorAgent: 'unknown',
    alerts: [],
  });
  const [loading, setLoading] = useState(false);
  const [escalationsLoading, setEscalationsLoading] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("queue");
  const [stats, setStats] = useState({
    total: 0,
    queued: 0,
    active: 0,
    completed: 0,
    failed: 0,
  });
  const [escalationStats, setEscalationStats] = useState({
    total: 0,
    active: 0,
    resolved: 0,
    pending: 0,
  });
  const [forecasts, setForecasts] = useState({
    recruitment: null,
    resources: null,
    revenue: null,
  });
  const [forecastsLoading, setForecastsLoading] = useState(false);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const response = await apiRequest("/admin/queue/tasks", {
        method: "GET",
      });

      if (response?.data?.tasks) {
        setTasks(response.data.tasks);
        calculateStats(response.data.tasks);
      }
    } catch (error) {
      console.error("Failed to load tasks", error);
      message.error("Failed to load message queue tasks");
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (taskList) => {
    const newStats = {
      total: taskList.length,
      queued: 0,
      active: 0,
      completed: 0,
      failed: 0,
    };

    taskList.forEach((task) => {
      const status = task.status?.toLowerCase();
      if (status === "queued") newStats.queued++;
      if (status === "active") newStats.active++;
      if (status === "completed") newStats.completed++;
      if (status === "failed") newStats.failed++;
    });

    setStats(newStats);
  };

  const loadEscalations = async () => {
    try {
      setEscalationsLoading(true);
      const response = await apiRequest("/admin/doctor-traces", {
        method: "GET",
      });

      if (response?.data?.traces) {
        setEscalations(response.data.traces);

        // Calculate escalation stats
        const newStats = {
          total: response.data.traces.length,
          active: response.data.traces.filter(t => t.status === 'ACTIVE').length,
          resolved: response.data.traces.filter(t => t.status === 'RESOLVED').length,
          pending: response.data.traces.filter(t => t.status === 'PENDING').length,
        };
        setEscalationStats(newStats);
      }
    } catch (error) {
      console.error("Failed to load escalations", error);
      message.error("Failed to load doctor escalations");
    } finally {
      setEscalationsLoading(false);
    }
  };

  const loadForecasts = async () => {
    try {
      setForecastsLoading(true);
      const [recruitmentRes, resourcesRes, revenueRes] = await Promise.all([
        apiRequest("/spartan/forecasting/recruitment/forecast", { method: "POST" }),
        apiRequest("/spartan/forecasting/resources/forecast", { method: "POST" }),
        apiRequest("/spartan/forecasting/revenue/forecast", { method: "POST" }),
      ]);

      setForecasts({
        recruitment: recruitmentRes?.data || null,
        resources: resourcesRes?.data || null,
        revenue: revenueRes?.data || null,
      });
    } catch (error) {
      console.error("Failed to load forecasts", error);
      message.error("Failed to load forecasting data");
    } finally {
      setForecastsLoading(false);
    }
  };

  const loadHealth = async () => {
    try {
      setHealthLoading(true);
      const response = await apiRequest("/admin/health", {
        method: "GET",
      });

      if (response?.data) {
        setHealth({
          database: response.data.database_status || 'unknown',
          messageQueue: response.data.queue_status || 'unknown',
          slmService: response.data.slm_status || 'unknown',
          doctorAgent: response.data.doctor_status || 'unknown',
          alerts: response.data.alerts || [],
        });
      }
    } catch (error) {
      console.error("Failed to load health data", error);
      // Don't show error message for health - it's auxiliary
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    // Load all data on mount
    loadTasks();
    loadEscalations();
    loadHealth();
    loadForecasts();

    // Auto-refresh all data every 10 seconds
    const interval = setInterval(() => {
      loadTasks();
      if (activeTab === "escalations") loadEscalations();
      if (activeTab === "health") loadHealth();
      if (activeTab === "forecasting") loadForecasts();
    }, 10000);

    return () => clearInterval(interval);
  }, [activeTab]);

  const handleRetryTask = async (taskId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${taskId}/retry`, {
        method: "POST",
      });
      message.success("Task retry queued");
      loadTasks();
    } catch (error) {
      console.error("Failed to retry task", error);
      message.error("Failed to retry task");
    }
  };

  const handleClearTask = async (taskId) => {
    try {
      await apiRequest(`/admin/queue/tasks/${taskId}/clear`, {
        method: "POST",
      });
      message.success("Task cleared");
      loadTasks();
    } catch (error) {
      console.error("Failed to clear task", error);
      message.error("Failed to clear task");
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "queued":
        return "blue";
      case "active":
        return "processing";
      case "completed":
        return "success";
      case "failed":
        return "error";
      default:
        return "default";
    }
  };

  const getStatusIcon = (status) => {
    if (status?.toLowerCase() === "failed") {
      return <ExclamationCircleOutlined />;
    }
    return null;
  };

  const getHealthColor = (status) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "up":
        return "success";
      case "degraded":
      case "warning":
        return "warning";
      case "down":
      case "error":
        return "error";
      default:
        return "default";
    }
  };

  const escalationColumns = [
    {
      title: "Message ID",
      dataIndex: "message_id",
      key: "message_id",
      width: 150,
      render: (id) => <code style={{ fontSize: "11px" }}>{id?.substring(0, 16)}...</code>,
    },
    {
      title: "Attempt",
      dataIndex: "attempt_number",
      key: "attempt_number",
      width: 80,
      render: (num) => <Tag color="blue">{num}</Tag>,
    },
    {
      title: "Strategy",
      dataIndex: "strategy",
      key: "strategy",
      width: 150,
      render: (strategy) => (
        <Tag>{strategy || "ESCALATE_TO_WROS"}</Tag>
      ),
    },
    {
      title: "Assigned To",
      dataIndex: "assigned_to_user",
      key: "assigned_to_user",
      width: 150,
      render: (user) => <span>{user?.name || "Unassigned"}</span>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status) => (
        <Tag color={status === 'RESOLVED' ? 'success' : status === 'ACTIVE' ? 'processing' : 'default'}>
          {status}
        </Tag>
      ),
    },
    {
      title: "WROS Ticket",
      dataIndex: "wros_ticket_id",
      key: "wros_ticket_id",
      width: 150,
      render: (ticketId) => ticketId ? <a href={`/tickets/${ticketId}`}>{ticketId}</a> : '-',
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date) =>
        date ? new Date(date).toLocaleString() : "-",
    },
  ];

  const columns = [
    {
      title: "Task ID",
      dataIndex: "task_id",
      key: "task_id",
      width: 200,
      render: (id) => <code style={{ fontSize: "11px" }}>{id?.substring(0, 20)}...</code>,
    },
    {
      title: "Task Name",
      dataIndex: "task_name",
      key: "task_name",
      width: 200,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status) => (
        <Tag color={getStatusColor(status)} icon={getStatusIcon(status)}>
          {status}
        </Tag>
      ),
    },
    {
      title: "Progress",
      dataIndex: "progress",
      key: "progress",
      width: 150,
      render: (progress) => (
        <Progress percent={progress || 0} size="small" />
      ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date) =>
        date
          ? new Date(date).toLocaleString()
          : "-",
    },
    {
      title: "Action",
      key: "action",
      width: 250,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedTask(record);
              setDrawerOpen(true);
            }}
          >
            View Messages
          </Button>
          {record.status?.toLowerCase() === "failed" && (
            <>
              <Button
                type="link"
                size="small"
                icon={<RedoOutlined />}
                onClick={() => handleRetryTask(record.task_id)}
              >
                Retry
              </Button>
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleClearTask(record.task_id)}
              >
                Clear
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <div>
        <h1>System Health Dashboard</h1>
        <Space style={{ marginBottom: 16 }}>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              loadTasks();
              if (activeTab === "escalations") loadEscalations();
              if (activeTab === "health") loadHealth();
              if (activeTab === "forecasting") loadForecasts();
            }}
            loading={loading || escalationsLoading || healthLoading || forecastsLoading}
          >
            Refresh
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "queue",
            label: "Message Queue",
            children: (
              <>
                <StatsContainer>
                  <Card>
                    <Statistic
                      title="Total Tasks"
                      value={stats.total}
                      valueStyle={{ color: "#1890ff" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Queued"
                      value={stats.queued}
                      valueStyle={{ color: "#1890ff" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Active"
                      value={stats.active}
                      valueStyle={{ color: "#faad14" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Completed"
                      value={stats.completed}
                      valueStyle={{ color: "#52c41a" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Failed"
                      value={stats.failed}
                      valueStyle={{ color: "#ff4d4f" }}
                    />
                  </Card>
                </StatsContainer>

                <Card>
                  <Spin spinning={loading}>
                    {tasks.length === 0 ? (
                      <Empty description="No tasks in queue" />
                    ) : (
                      <Table
                        columns={columns}
                        dataSource={tasks}
                        rowKey="task_id"
                        pagination={{ pageSize: 20 }}
                        scroll={{ x: 1200 }}
                      />
                    )}
                  </Spin>
                </Card>
              </>
            ),
          },
          {
            key: "escalations",
            label: `Doctor Agent Escalations (${escalationStats.active})`,
            children: (
              <>
                <StatsContainer>
                  <Card>
                    <Statistic
                      title="Total Escalations"
                      value={escalationStats.total}
                      valueStyle={{ color: "#1890ff" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Active"
                      value={escalationStats.active}
                      valueStyle={{ color: "#ff4d4f" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Pending"
                      value={escalationStats.pending}
                      valueStyle={{ color: "#faad14" }}
                    />
                  </Card>
                  <Card>
                    <Statistic
                      title="Resolved"
                      value={escalationStats.resolved}
                      valueStyle={{ color: "#52c41a" }}
                    />
                  </Card>
                </StatsContainer>

                <Card title="Doctor Agent Traces" style={{ marginTop: 16 }}>
                  <Spin spinning={escalationsLoading}>
                    {escalations.length === 0 ? (
                      <Empty description="No escalations" />
                    ) : (
                      <Table
                        columns={escalationColumns}
                        dataSource={escalations}
                        rowKey="id"
                        pagination={{ pageSize: 20 }}
                        scroll={{ x: 1400 }}
                      />
                    )}
                  </Spin>
                </Card>
              </>
            ),
          },
          {
            key: "health",
            label: "System Health",
            children: (
              <>
                <Spin spinning={healthLoading}>
                  {health.alerts && health.alerts.length > 0 && (
                    <Alert
                      message="System Alerts"
                      description={
                        <ul style={{ marginBottom: 0 }}>
                          {health.alerts.map((alert, idx) => (
                            <li key={idx}>{alert}</li>
                          ))}
                        </ul>
                      }
                      type="warning"
                      showIcon
                      style={{ marginBottom: 16 }}
                    />
                  )}

                  <Card title="Service Status" style={{ marginBottom: 16 }}>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Card type="inner">
                          <Space direction="vertical" style={{ width: "100%" }}>
                            <div>
                              <strong>Database:</strong>{" "}
                              <Tag color={getHealthColor(health.database)}>
                                {health.database}
                              </Tag>
                            </div>
                            <div>
                              <strong>Message Queue:</strong>{" "}
                              <Tag color={getHealthColor(health.messageQueue)}>
                                {health.messageQueue}
                              </Tag>
                            </div>
                          </Space>
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card type="inner">
                          <Space direction="vertical" style={{ width: "100%" }}>
                            <div>
                              <strong>SLM Service:</strong>{" "}
                              <Tag color={getHealthColor(health.slmService)}>
                                {health.slmService}
                              </Tag>
                            </div>
                            <div>
                              <strong>Doctor Agent:</strong>{" "}
                              <Tag color={getHealthColor(health.doctorAgent)}>
                                {health.doctorAgent}
                              </Tag>
                            </div>
                          </Space>
                        </Card>
                      </Col>
                    </Row>
                  </Card>
                </Spin>
              </>
            ),
          },
          {
            key: "forecasting",
            label: "Autonomous Forecasting",
            children: (
              <>
                <Spin spinning={forecastsLoading}>
                  <Row gutter={16} style={{ marginBottom: 24 }}>
                    <Col span={8}>
                      <Card>
                        <h3 style={{ marginTop: 0 }}>Recruitment Forecast</h3>
                        {forecasts.recruitment ? (
                          <>
                            <p>
                              <strong>Status:</strong>{" "}
                              <Tag color={
                                forecasts.recruitment.gap_analysis?.status === 'CRITICAL' ? 'red' :
                                forecasts.recruitment.gap_analysis?.status === 'BEHIND' ? 'orange' :
                                'green'
                              }>
                                {forecasts.recruitment.gap_analysis?.status}
                              </Tag>
                            </p>
                            <p>
                              <strong>Achievement:</strong> {forecasts.recruitment.current_state?.achievement_percent?.toFixed(1)}%
                            </p>
                            <p>
                              <strong>Needed:</strong> +{forecasts.recruitment.gap_analysis?.candidates_needed} candidates
                            </p>
                            <p>
                              <strong>Escalate to:</strong> {forecasts.recruitment.escalation_node}
                            </p>
                          </>
                        ) : (
                          <Empty description="Loading..." />
                        )}
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card>
                        <h3 style={{ marginTop: 0 }}>Resource Forecast</h3>
                        {forecasts.resources ? (
                          <>
                            <p>
                              <strong>Status:</strong>{" "}
                              <Tag color={
                                forecasts.resources.gap_analysis?.status === 'UNDERSTAFFED' ? 'red' : 'green'
                              }>
                                {forecasts.resources.gap_analysis?.status}
                              </Tag>
                            </p>
                            <p>
                              <strong>Utilization:</strong> {forecasts.resources.current_state?.utilization_percent}%
                            </p>
                            <p>
                              <strong>Demand Fulfillment:</strong> {forecasts.resources.current_state?.demand_fulfillment_percent}%
                            </p>
                            <p>
                              <strong>Escalate to:</strong> {forecasts.resources.escalation_node}
                            </p>
                          </>
                        ) : (
                          <Empty description="Loading..." />
                        )}
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card>
                        <h3 style={{ marginTop: 0 }}>Revenue Forecast</h3>
                        {forecasts.revenue ? (
                          <>
                            <p>
                              <strong>Status:</strong>{" "}
                              <Tag color={
                                forecasts.revenue.gap_analysis?.status === 'CRITICAL' ? 'red' : 'orange'
                              }>
                                {forecasts.revenue.gap_analysis?.status}
                              </Tag>
                            </p>
                            <p>
                              <strong>Revenue Gap:</strong> ${(forecasts.revenue.gap_analysis?.revenue_gap / 1_000_000).toFixed(1)}M
                            </p>
                            <p>
                              <strong>Months of Runway:</strong> {forecasts.revenue.gap_analysis?.months_of_runway?.toFixed(2)}
                            </p>
                            <p>
                              <strong>Escalate to:</strong> {forecasts.revenue.escalation_node}
                            </p>
                          </>
                        ) : (
                          <Empty description="Loading..." />
                        )}
                      </Card>
                    </Col>
                  </Row>

                  <Card title="Forecast Recommendations">
                    {forecasts.recruitment?.resource_options && (
                      <div style={{ marginBottom: 16 }}>
                        <h4>Recruitment Options:</h4>
                        {forecasts.recruitment.resource_options.map((opt, idx) => (
                          <div key={idx} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #eee' }}>
                            <p><strong>{opt.option}</strong> - {opt.cost}</p>
                            <p><small>{opt.expected_result}</small></p>
                          </div>
                        ))}
                      </div>
                    )}

                    {forecasts.resources?.resource_options && (
                      <div style={{ marginBottom: 16 }}>
                        <h4>Resource Options:</h4>
                        {forecasts.resources.resource_options.map((opt, idx) => (
                          <div key={idx} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #eee' }}>
                            <p><strong>{opt.option}</strong> - {opt.cost}</p>
                            <p><small>{opt.expected_result}</small></p>
                          </div>
                        ))}
                      </div>
                    )}

                    {forecasts.revenue?.revenue_options && (
                      <div>
                        <h4>Revenue Options:</h4>
                        {forecasts.revenue.revenue_options.map((opt, idx) => (
                          <div key={idx} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #eee' }}>
                            <p><strong>{opt.option}</strong> - {opt.value}</p>
                            <p><small>Probability: {opt.probability}, Timeline: {opt.timeline}</small></p>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                </Spin>
              </>
            ),
          },
        ]}
      />

      <Drawer
        title={`Task Messages: ${selectedTask?.task_name}`}
        placement="right"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={600}
      >
        {selectedTask && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h3>Task Details</h3>
              <p><strong>Task ID:</strong> <code>{selectedTask.task_id}</code></p>
              <p><strong>Status:</strong> <Tag color={getStatusColor(selectedTask.status)}>{selectedTask.status}</Tag></p>
              <p><strong>Created:</strong> {new Date(selectedTask.created_at).toLocaleString()}</p>
              <p><strong>Progress:</strong> <Progress percent={selectedTask.progress || 0} /></p>
            </div>

            <div>
              <h3>Messages & Events</h3>
              {selectedTask.messages && selectedTask.messages.length > 0 ? (
                <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                  {selectedTask.messages.map((msg, idx) => (
                    <Card
                      key={idx}
                      size="small"
                      style={{ marginBottom: 12 }}
                      type={msg.level === "error" ? "error" : "default"}
                    >
                      <p style={{ margin: 0, marginBottom: 4 }}>
                        <strong>
                          <Tag color={msg.level === "error" ? "red" : "blue"}>
                            {msg.level?.toUpperCase()}
                          </Tag>
                        </strong>
                        <small style={{ marginLeft: 8 }}>
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </small>
                      </p>
                      <p style={{ margin: 0, fontFamily: "monospace", fontSize: "12px", whiteSpace: "pre-wrap" }}>
                        {msg.message}
                      </p>
                    </Card>
                  ))}
                </div>
              ) : (
                <Empty description="No messages yet" />
              )}
            </div>

            {selectedTask.status?.toLowerCase() === "failed" && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #ddd" }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<RedoOutlined />}
                    onClick={() => {
                      handleRetryTask(selectedTask.task_id);
                      setDrawerOpen(false);
                    }}
                  >
                    Retry Task
                  </Button>
                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      handleClearTask(selectedTask.task_id);
                      setDrawerOpen(false);
                    }}
                  >
                    Clear Task
                  </Button>
                </Space>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </PageContainer>
  );
}

export default MessageQueueDashboard;
